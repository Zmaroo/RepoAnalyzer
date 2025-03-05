"""
Pattern validation module to ensure the integrity of pattern definitions.

This module provides tools to validate pattern definitions before they are used
in the pattern processor, helping to catch errors early in the development process.
"""

import re
import asyncio
from typing import Dict, Any, List, Optional, Set, Callable
from parsers.types import PatternCategory, PatternDefinition, QueryPattern
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary, ErrorSeverity
from utils.logger import log
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

class PatternValidationError(Exception):
    """Exception raised for pattern validation errors."""
    pass

class PatternValidator:
    """Validates pattern definitions to ensure they are well-formed."""
    
    def __init__(self):
        """Initialize the pattern validator."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize pattern validator resources."""
        if not self._initialized:
            try:
                # No special initialization needed yet
                self._initialized = True
                log("Pattern validator initialized", level="info")
            except Exception as e:
                log(f"Error initializing pattern validator: {e}", level="error")
                raise
    
    async def validate_pattern_definition(self, pattern_name: str, definition: PatternDefinition) -> List[str]:
        """
        Validate a pattern definition for completeness and correctness.
        
        Args:
            pattern_name: The name/identifier of the pattern
            definition: The pattern definition to validate
            
        Returns:
            A list of validation error messages (empty if no errors)
        """
        if not self._initialized:
            await self.initialize()
            
        errors = []
        
        # Check for required attributes
        if not hasattr(definition, 'pattern') or not definition.pattern:
            errors.append(f"Pattern '{pattern_name}' is missing a pattern string")
        
        # Check that pattern is valid regex (if it's a string)
        if hasattr(definition, 'pattern') and isinstance(definition.pattern, str):
            try:
                future = submit_async_task(re.compile(definition.pattern))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                except re.error as e:
                    errors.append(f"Pattern '{pattern_name}' has invalid regex: {str(e)}")
                finally:
                    self._pending_tasks.remove(future)
            except Exception as e:
                errors.append(f"Pattern '{pattern_name}' compilation failed: {str(e)}")
        
        # Ensure extract method is callable if provided
        if hasattr(definition, 'extract') and definition.extract is not None and not callable(definition.extract):
            errors.append(f"Pattern '{pattern_name}' has non-callable extract method")
        
        return errors
    
    async def validate_query_pattern(self, pattern_name: str, definition: QueryPattern) -> List[str]:
        """
        Validate a query pattern for completeness and correctness.
        
        Args:
            pattern_name: The name/identifier of the pattern
            definition: The query pattern to validate
            
        Returns:
            A list of validation error messages (empty if no errors)
        """
        if not self._initialized:
            await self.initialize()
            
        errors = []
        
        # Check for required attributes
        if not hasattr(definition, 'query') or not definition.query:
            errors.append(f"Query pattern '{pattern_name}' is missing a query string")
        
        # Ensure extract method is callable if provided
        if hasattr(definition, 'extract') and definition.extract is not None and not callable(definition.extract):
            errors.append(f"Query pattern '{pattern_name}' has non-callable extract method")
        
        return errors
    
    async def validate_language_patterns(self, language: str, patterns: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate all patterns for a specific language.
        
        Args:
            language: The language identifier
            patterns: Dictionary of pattern definitions for the language
            
        Returns:
            Dictionary mapping pattern names to lists of error messages
        """
        if not self._initialized:
            await self.initialize()
            
        validation_results = {}
        
        for pattern_name, definition in patterns.items():
            future = submit_async_task(
                self.validate_query_pattern(pattern_name, definition) 
                if hasattr(definition, 'query') 
                else self.validate_pattern_definition(pattern_name, definition)
            )
            self._pending_tasks.add(future)
            try:
                errors = await asyncio.wrap_future(future)
                if errors:
                    validation_results[pattern_name] = errors
            finally:
                self._pending_tasks.remove(future)
        
        return validation_results
    
    def validate_pattern_naming(self, pattern_name: str) -> List[str]:
        """
        Validate pattern naming conventions.
        
        Args:
            pattern_name: The pattern name to validate
            
        Returns:
            List of validation error messages (empty if no errors)
        """
        errors = []
        
        # Check naming conventions
        if not pattern_name:
            errors.append("Pattern name cannot be empty")
        
        if ' ' in pattern_name:
            errors.append(f"Pattern name '{pattern_name}' contains spaces (use underscores instead)")
        
        # Check for snake_case: all lowercase with underscores
        if not pattern_name.islower() or (pattern_name.isalnum() and not pattern_name.islower()):
            errors.append(f"Pattern name '{pattern_name}' should use snake_case (all lowercase with underscores)")
        
        return errors

    def check_duplicate_patterns(self, patterns: Dict[str, Any]) -> List[str]:
        """
        Check for duplicate pattern definitions.
        
        Args:
            patterns: Dictionary of all pattern definitions
            
        Returns:
            List of validation warnings about potential duplicates
        """
        warnings = []
        
        # Check for potentially duplicate regex patterns
        pattern_strings = {}
        
        for name, definition in patterns.items():
            if hasattr(definition, 'pattern') and isinstance(definition.pattern, str):
                if definition.pattern in pattern_strings:
                    warnings.append(
                        f"Potential duplicate pattern: '{name}' has the same regex as '{pattern_strings[definition.pattern]}'"
                    )
                else:
                    pattern_strings[definition.pattern] = name
        
        return warnings

    async def cleanup(self):
        """Clean up pattern validator resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Pattern validator cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up pattern validator: {e}", level="error")

# Global instance
pattern_validator = PatternValidator()

async def validate_all_patterns(patterns_by_language: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    """
    Validate all patterns across all languages.
    
    Args:
        patterns_by_language: Dictionary mapping languages to their pattern definitions
        
    Returns:
        Nested dictionary of validation errors by language and pattern name
    """
    if not pattern_validator._initialized:
        await pattern_validator.initialize()
        
    validation_results = {}
    
    for language, patterns in patterns_by_language.items():
        future = submit_async_task(pattern_validator.validate_language_patterns(language, patterns))
        pattern_validator._pending_tasks.add(future)
        try:
            language_results = await asyncio.wrap_future(future)
            
            # Add naming convention validation
            for pattern_name in patterns.keys():
                naming_errors = pattern_validator.validate_pattern_naming(pattern_name)
                if naming_errors:
                    if pattern_name in language_results:
                        language_results[pattern_name].extend(naming_errors)
                    else:
                        language_results[pattern_name] = naming_errors
            
            if language_results:
                validation_results[language] = language_results
        finally:
            pattern_validator._pending_tasks.remove(future)
    
    return validation_results

def report_validation_results(validation_results: Dict[str, Dict[str, List[str]]]) -> str:
    """
    Generate a human-readable report of validation results.
    
    Args:
        validation_results: Validation results from validate_all_patterns
        
    Returns:
        String containing a formatted validation report
    """
    if not validation_results:
        return "All patterns passed validation."
    
    report = ["Pattern Validation Results:", ""]
    
    error_count = 0
    for language, pattern_errors in validation_results.items():
        language_error_count = sum(len(errors) for errors in pattern_errors.values())
        error_count += language_error_count
        
        report.append(f"Language: {language} ({language_error_count} errors)")
        report.append("-" * (len(language) + 14))
        
        for pattern_name, errors in pattern_errors.items():
            report.append(f"  Pattern '{pattern_name}':")
            for error in errors:
                report.append(f"    - {error}")
            report.append("")
        
        report.append("")
    
    report.insert(1, f"Found {error_count} errors across {len(validation_results)} languages.")
    
    return "\n".join(report) 