"""[6.0] Pattern processing and validation.

This module provides pattern processing capabilities for code analysis and manipulation.
Core pattern processing functionality separated from AI capabilities.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Union, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
import re
import time
import importlib
import numpy as np
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    ParserType, PatternCategory, PatternPurpose, FileType, 
    PatternDefinition, QueryPattern, AIContext, 
    AIProcessingResult, PatternType, PatternRelationType,
    FeatureCategory, ParserResult, PatternValidationResult,
    ExtractedFeatures, Pattern
)
from parsers.models import (
    PatternMatch, PATTERN_CATEGORIES, ProcessedPattern, 
    QueryResult, PatternRelationship
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.base_parser import BaseParser
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from parsers.language_mapping import normalize_language_name
from parsers.tree_sitter_parser import QueryPatternRegistry, get_tree_sitter_parser
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.cache import UnifiedCache, cache_coordinator
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.shutdown import register_shutdown_handler
from db.pattern_storage import PatternStorageMetrics, get_pattern_storage
from db.transaction import transaction_scope
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
import traceback
import os
import psutil
from parsers.query_patterns import (
    create_pattern,
    validate_pattern,
    is_language_supported,
    get_parser_type_for_language
)

@dataclass
class PatternProcessor(BaseParser):
    """Pattern processing management.
    
    This class manages pattern processing for languages,
    integrating with the parser system for efficient pattern handling.
    
    Attributes:
        language_id (str): The identifier for the language
        patterns (Dict[str, Pattern]): Map of pattern names to patterns
        _pattern_cache (UnifiedCache): Cache for processed patterns
        _query_registry (Optional[QueryPatternRegistry]): Registry for tree-sitter query patterns
    """
    
    def __init__(self, language_id: str):
        """Initialize pattern processor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.patterns = {}
        self._pattern_cache = None
        self._query_registry = None  # Will be initialized if tree-sitter is available
        self._processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "processing_times": []
        }
        
        # Pattern tracking
        self._pattern_usage_stats = {}
        self._pattern_success_rates = {}
        self._adaptive_thresholds = {}
        self._learning_enabled = True
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize pattern processor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"pattern_processor_initialization_{self.language_id}"):
                # Initialize cache
                self._pattern_cache = UnifiedCache(f"pattern_processor_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"pattern_processor_{self.language_id}",
                    self._pattern_cache
                )
                
                # Initialize query registry if tree-sitter is available
                try:
                    ts_parser = await get_tree_sitter_parser(self.language_id)
                    if ts_parser:
                        self._query_registry = QueryPatternRegistry(self.language_id)
                        await self._query_registry.initialize()
                        await log(f"QueryPatternRegistry initialized for {self.language_id}", level="info")
                except Exception as e:
                    await log(f"Could not initialize QueryPatternRegistry: {e}", level="warning")
                    # Continue initialization - tree-sitter is optional
                
                # Load patterns through async_runner
                init_task = submit_async_task(self._load_patterns())
                await asyncio.wrap_future(init_task)
                
                if not self.patterns:
                    raise ProcessingError(f"Failed to load patterns for {self.language_id}")
                
                # Register tree-sitter patterns with the registry if available
                if self._query_registry:
                    await self._register_patterns_with_registry()
                
                await log(f"Pattern processor initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing pattern processor: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"pattern_processor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"processor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize pattern processor for {self.language_id}: {e}")
    
    async def _register_patterns_with_registry(self) -> None:
        """Register patterns with QueryPatternRegistry."""
        if not self._query_registry:
            return
            
        try:
            # Register tree-sitter patterns with registry
            for name, pattern in self.patterns.items():
                if hasattr(pattern, 'tree_sitter_query') and pattern.tree_sitter_query:
                    # Extract category from pattern if available
                    category = getattr(pattern, 'category', PatternCategory.SYNTAX)
                    category_str = category.value if hasattr(category, 'value') else str(category)
                    
                    # Register pattern with registry
                    self._query_registry.register_pattern(category_str, pattern.tree_sitter_query)
                    await log(f"Registered pattern {name} with QueryPatternRegistry", level="debug")
                    
        except Exception as e:
            await log(f"Error registering patterns with registry: {e}", level="warning")
    
    async def _load_patterns(self) -> None:
        """Load patterns from storage."""
        try:
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_patterns_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load patterns
                patterns_result = await txn.fetch("""
                    SELECT pattern_name, pattern_data FROM language_patterns
                    WHERE language_id = $1
                """, self.language_id)
                
                if patterns_result:
                    self.patterns = {
                        row["pattern_name"]: Pattern(**row["pattern_data"])
                        for row in patterns_result
                    }
                
                # Record transaction metrics
                await txn.record_operation("load_patterns_complete", {
                    "language_id": self.language_id,
                    "pattern_count": len(self.patterns),
                    "end_time": time.time()
                })
                
        except Exception as e:
            await log(f"Error loading patterns: {e}", level="error")
            raise ProcessingError(f"Failed to load patterns: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def process_pattern(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process a pattern.
        
        Args:
            pattern_name: The name of the pattern to process
            content: The content to process
            context: The processing context
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"pattern_processing_{self.language_id}"):
                # Check cache first
                cache_key = f"pattern:{self.language_id}:{pattern_name}:{hash(content)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Process through async_runner
                process_task = submit_async_task(
                    self._process_pattern_content(pattern_name, content, context)
                )
                result = await asyncio.wrap_future(process_task)
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(f"Pattern processed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error processing pattern: {e}", level="error")
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"pattern_processing_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "content_size": len(content)
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _process_pattern_content(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process pattern content."""
        try:
            start_time = time.time()
            
            # Get pattern
            pattern = self.patterns.get(pattern_name)
            if not pattern:
                return PatternValidationResult(
                    is_valid=False,
                    errors=[f"Pattern {pattern_name} not found"]
                )
            
            # Process pattern
            matches = await pattern.match(content, context)
            
            # Update timing stats
            processing_time = time.time() - start_time
            self._processing_stats["processing_times"].append(processing_time)
            
            # Update pattern stats
            await self._update_pattern_stats(
                pattern_name,
                bool(matches),
                processing_time,
                len(matches) if matches else 0
            )
            
            return PatternValidationResult(
                is_valid=bool(matches),
                errors=[] if matches else ["No matches found"],
                validation_time=processing_time
            )
            
        except Exception as e:
            await log(f"Error processing pattern content: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _update_pattern_stats(
        self,
        pattern_name: str,
        success: bool,
        processing_time: float,
        matches_found: int
    ) -> None:
        """Update pattern usage statistics for learning."""
        if not self._learning_enabled:
            return
            
        if pattern_name not in self._pattern_usage_stats:
            self._pattern_usage_stats[pattern_name] = {
                "uses": 0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0,
                "matches_found": 0
            }
        
        stats = self._pattern_usage_stats[pattern_name]
        stats["uses"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Update moving averages
        stats["avg_time"] = (stats["avg_time"] * (stats["uses"] - 1) + processing_time) / stats["uses"]
        stats["matches_found"] = (stats["matches_found"] * (stats["uses"] - 1) + matches_found) / stats["uses"]
        
        # Update success rate
        self._pattern_success_rates[pattern_name] = stats["successes"] / stats["uses"]
        
        # Adjust thresholds based on pattern performance
        if stats["uses"] > 100:  # Wait for sufficient data
            if self._pattern_success_rates[pattern_name] < 0.3:  # Low success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 0.8,  # Reduce time allowance
                    "min_matches": stats["matches_found"] * 1.2  # Require more matches
                }
            elif self._pattern_success_rates[pattern_name] > 0.8:  # High success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 1.2,  # Allow more time
                    "min_matches": stats["matches_found"] * 0.8  # Accept fewer matches
                }
    
    async def _cleanup(self) -> None:
        """Clean up pattern processor resources."""
        try:
            # Clean up cache
            if self._pattern_cache:
                await cache_coordinator.unregister_cache(f"pattern_processor_{self.language_id}")
                self._pattern_cache = None
            
            # Save processing stats using distributed transaction
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("pattern_processor_cleanup_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Save processing stats
                await txn.execute("""
                    INSERT INTO pattern_processor_stats (
                        timestamp, language_id,
                        total_processed, successful_processing,
                        failed_processing, avg_processing_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._processing_stats["total_processed"],
                    self._processing_stats["successful_processing"],
                    self._processing_stats["failed_processing"],
                    sum(self._processing_stats["processing_times"]) / len(self._processing_stats["processing_times"])
                    if self._processing_stats["processing_times"] else 0
                ))
                
                # Save pattern stats
                for pattern_name, stats in self._pattern_usage_stats.items():
                    await txn.execute("""
                        INSERT INTO pattern_usage_stats (
                            timestamp, language_id, pattern_name,
                            uses, successes, failures,
                            avg_time, matches_found
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, (
                        time.time(),
                        self.language_id,
                        pattern_name,
                        stats["uses"],
                        stats["successes"],
                        stats["failures"],
                        stats["avg_time"],
                        stats["matches_found"]
                    ))
                
                # Record transaction metrics
                await txn.record_operation("pattern_processor_cleanup_complete", {
                    "language_id": self.language_id,
                    "pattern_count": len(self._pattern_usage_stats),
                    "end_time": time.time()
                })
            
            await log(f"Pattern processor cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern processor: {e}")

    async def process_tree_sitter_pattern(
        self,
        pattern_name: str,
        tree: Any,
        source_code: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process a pattern using tree-sitter query.
        
        Args:
            pattern_name: The name of the pattern to process
            tree: The tree-sitter tree
            source_code: The source code
            context: The processing context
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"tree_sitter_pattern_processing_{self.language_id}"):
                # Check cache first
                cache_key = f"ts_pattern:{self.language_id}:{pattern_name}:{hash(source_code)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Get pattern
                pattern = self.patterns.get(pattern_name)
                if not pattern:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=[f"Pattern {pattern_name} not found"]
                    )
                
                # Get tree-sitter query string - first try from registry, then from pattern
                query_string = None
                
                # If we have a query registry, try to get the pattern from there
                if self._query_registry:
                    # Extract category from pattern if available
                    category = getattr(pattern, 'category', PatternCategory.SYNTAX)
                    category_str = category.value if hasattr(category, 'value') else str(category)
                    
                    # Try to get pattern from registry
                    query_string = self._query_registry.get_pattern(category_str)
                
                # If not found in registry, use pattern's tree_sitter_query
                if not query_string and hasattr(pattern, 'tree_sitter_query'):
                    query_string = pattern.tree_sitter_query
                    
                if not query_string:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=["No tree-sitter query available for this pattern"]
                    )
                
                # Process through tree-sitter parser
                ts_parser = await get_tree_sitter_parser(self.language_id)
                if not ts_parser:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=["Tree-sitter parser not available for this language"]
                    )
                
                # Execute optimized query with performance monitoring
                start_time = time.time()
                
                # First analyze the query performance characteristics
                query_analysis = await ts_parser._monitor_query_performance(query_string, tree)
                
                # Choose appropriate execution strategy based on complexity
                complexity = query_analysis.get('estimated_complexity', 0)
                if complexity > 100:  # High complexity query
                    # Use optimized query execution with limits
                    matches = await ts_parser._execute_optimized_query(
                        query_string, 
                        tree,
                        match_limit=1000,  # Limit matches to prevent excessive resource usage
                        timeout_micros=50000  # 50ms timeout
                    )
                else:
                    # Standard query execution for simpler queries
                    matches = await ts_parser._execute_query(query_string, tree)
                    
                processing_time = time.time() - start_time
                
                # Update pattern stats
                await self._update_pattern_stats(
                    pattern_name,
                    bool(matches),
                    processing_time,
                    sum(len(nodes) for nodes in matches.values()) if matches else 0
                )
                
                # Create result
                result = PatternValidationResult(
                    is_valid=bool(matches),
                    errors=[] if matches else ["No matches found"],
                    validation_time=processing_time,
                    matches=[{
                        'capture': capture_name,
                        'nodes': [{
                            'text': node['text'],
                            'start': node['start_point'],
                            'end': node['end_point'],
                            'type': node['type']
                        } for node in nodes]
                    } for capture_name, nodes in matches.items()],
                    # Add performance metrics
                    performance_metrics=query_analysis
                )
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                return result
                
        except Exception as e:
            await log(f"Error processing tree-sitter pattern: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )

    @handle_async_errors(error_types=ProcessingError)
    async def test_pattern(
        self,
        pattern_name: str,
        source_code: str,
        is_tree_sitter: bool = False
    ) -> Dict[str, Any]:
        """Test a pattern against source code.
        
        This method is used for diagnostics and validation to verify
        that patterns match as expected.
        
        Args:
            pattern_name: The name of the pattern to test
            source_code: The source code to test against
            is_tree_sitter: Whether to use tree-sitter for matching
            
        Returns:
            Dict[str, Any]: Test results including matches, performance metrics, and validation
        """
        try:
            async with AsyncErrorBoundary(f"pattern_testing_{self.language_id}"):
                # Get pattern
                pattern = self.patterns.get(pattern_name)
                if not pattern:
                    return {
                        "success": False,
                        "errors": [f"Pattern {pattern_name} not found"]
                    }
                
                # Create context
                context = AIContext(
                    language_id=self.language_id,
                    file_type=FileType.CODE,
                    interaction_type="testing"
                )
                
                # If tree-sitter testing
                if is_tree_sitter:
                    if not hasattr(pattern, 'tree_sitter_query') or not pattern.tree_sitter_query:
                        return {
                            "success": False,
                            "errors": ["No tree-sitter query available for this pattern"]
                        }
                    
                    # Use tree-sitter parser to test the query
                    ts_parser = await get_tree_sitter_parser(self.language_id)
                    if not ts_parser:
                        return {
                            "success": False,
                            "errors": ["Tree-sitter parser not available for this language"]
                        }
                    
                    # Test query
                    test_result = await ts_parser.test_query(pattern.tree_sitter_query, source_code)
                    
                    # Add pattern details to result
                    test_result["pattern_name"] = pattern_name
                    test_result["pattern_type"] = "tree_sitter"
                    return test_result
                
                # For regex patterns
                start_time = time.time()
                validation_result = await self.process_pattern(pattern_name, source_code, context)
                processing_time = time.time() - start_time
                
                # Return formatted results
                return {
                    "success": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "matches": validation_result.matches,
                    "performance": {
                        "execution_time_ms": processing_time * 1000
                    },
                    "pattern_name": pattern_name,
                    "pattern_type": "regex"
                }
                
        except Exception as e:
            await log(f"Error testing pattern: {e}", level="error")
            return {
                "success": False,
                "errors": [str(e)],
                "pattern_name": pattern_name
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def validate_pattern_syntax(
        self,
        pattern_name: str
    ) -> Dict[str, Any]:
        """Validate the syntax of a pattern.
        
        Args:
            pattern_name: The name of the pattern to validate
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            # Get pattern
            pattern = self.patterns.get(pattern_name)
            if not pattern:
                return {
                    "valid": False,
                    "errors": [f"Pattern {pattern_name} not found"]
                }
            
            # For tree-sitter patterns
            if hasattr(pattern, 'tree_sitter_query') and pattern.tree_sitter_query:
                ts_parser = await get_tree_sitter_parser(self.language_id)
                if not ts_parser:
                    return {
                        "valid": False,
                        "errors": ["Tree-sitter parser not available for this language"]
                    }
                
                # Analyze query structure
                query_analysis = ts_parser.analyze_query(pattern.tree_sitter_query)
                
                # Return validation results
                return {
                    "valid": query_analysis.get("is_valid", False),
                    "errors": query_analysis.get("errors", []),
                    "warnings": query_analysis.get("warnings", []),
                    "pattern_type": "tree_sitter",
                    "pattern_name": pattern_name,
                    "captures": query_analysis.get("captures", []),
                    "complexity": query_analysis.get("complexity", 0)
                }
            
            # For regex patterns
            try:
                # Try to compile the regex
                if hasattr(pattern, 'pattern'):
                    re.compile(pattern.pattern)
                    return {
                        "valid": True,
                        "errors": [],
                        "pattern_type": "regex",
                        "pattern_name": pattern_name
                    }
                else:
                    return {
                        "valid": False, 
                        "errors": ["No pattern string found"], 
                        "pattern_name": pattern_name
                    }
            except re.error as e:
                return {
                    "valid": False,
                    "errors": [f"Invalid regex: {str(e)}"],
                    "pattern_type": "regex",
                    "pattern_name": pattern_name
                }
                
        except Exception as e:
            await log(f"Error validating pattern syntax: {e}", level="error")
            return {
                "valid": False,
                "errors": [str(e)],
                "pattern_name": pattern_name
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def export_patterns(
        self,
        format_type: str = "dict",
        pattern_type: str = "all"
    ) -> Union[Dict[str, Any], str]:
        """Export patterns in the requested format.
        
        Args:
            format_type: Format to export ("dict", "json", or "yaml")
            pattern_type: Type of patterns to export ("all", "tree_sitter", or "regex")
            
        Returns:
            Union[Dict[str, Any], str]: Exported patterns
        """
        try:
            # Export tree-sitter patterns if requested
            if pattern_type in ["all", "tree_sitter"] and self._query_registry:
                ts_parser = await get_tree_sitter_parser(self.language_id)
                if ts_parser:
                    # Use tree-sitter's export functionality
                    ts_patterns = await ts_parser.export_query_patterns(format_type)
                    
                    # If not returning tree-sitter patterns only, continue to add regex patterns
                    if pattern_type == "tree_sitter":
                        return ts_patterns
            else:
                ts_patterns = {} if format_type == "dict" else "{}" if format_type == "json" else ""
            
            # Export regex patterns if requested
            if pattern_type in ["all", "regex"]:
                import json
                import yaml
                
                # Collect regex patterns
                regex_patterns = {}
                for name, pattern in self.patterns.items():
                    # Skip if it's a tree-sitter pattern and we've already included it
                    if hasattr(pattern, 'tree_sitter_query') and pattern.tree_sitter_query and pattern_type == "all":
                        continue
                    
                    # Add regex pattern
                    if hasattr(pattern, 'pattern'):
                        regex_patterns[name] = {
                            "pattern": pattern.pattern,
                            "category": getattr(pattern, 'category', PatternCategory.SYNTAX).value 
                                if hasattr(getattr(pattern, 'category', None), 'value') else str(getattr(pattern, 'category', "")),
                            "purpose": getattr(pattern, 'purpose', PatternPurpose.UNDERSTANDING).value
                                if hasattr(getattr(pattern, 'purpose', None), 'value') else str(getattr(pattern, 'purpose', "")),
                            "language_id": self.language_id
                        }
                
                # Return in requested format
                if format_type == "dict":
                    return {**ts_patterns, **regex_patterns} if isinstance(ts_patterns, dict) else regex_patterns
                elif format_type == "json":
                    return json.dumps({**json.loads(ts_patterns), **regex_patterns}, indent=2) if isinstance(ts_patterns, str) else json.dumps(regex_patterns, indent=2)
                elif format_type == "yaml":
                    return yaml.dump({**yaml.safe_load(ts_patterns), **regex_patterns}, default_flow_style=False) if isinstance(ts_patterns, str) else yaml.dump(regex_patterns, default_flow_style=False)
                else:
                    return {**ts_patterns, **regex_patterns} if isinstance(ts_patterns, dict) else regex_patterns
            
            # If only tree-sitter and we didn't return earlier, return empty result
            return {} if format_type == "dict" else "{}" if format_type == "json" else ""
            
        except Exception as e:
            await log(f"Error exporting patterns: {e}", level="error")
            return {} if format_type == "dict" else "{}" if format_type == "json" else ""
            
    @handle_async_errors(error_types=ProcessingError)
    async def get_patterns_for_category(
        self,
        category: Union[FeatureCategory, PatternCategory],
        purpose: Optional[PatternPurpose] = None,
        language_id: Optional[str] = None,
        parser_type: Optional[ParserType] = None
    ) -> List[Dict[str, Any]]:
        """Get patterns for a specific category.
        
        Args:
            category: Category to get patterns for
            purpose: Purpose filter (optional)
            language_id: Language filter (optional)
            parser_type: Parser type filter (optional)
            
        Returns:
            List[Dict[str, Any]]: List of patterns matching the criteria
        """
        result = []
        
        # Convert FeatureCategory to PatternCategory if needed
        if isinstance(category, FeatureCategory):
            # Map FeatureCategory to PatternCategory (simplified mapping)
            category_map = {
                FeatureCategory.SYNTAX: PatternCategory.SYNTAX,
                FeatureCategory.SEMANTICS: PatternCategory.SEMANTICS,
                FeatureCategory.DOCUMENTATION: PatternCategory.DOCUMENTATION,
                FeatureCategory.METRICS: PatternCategory.METRICS
            }
            pattern_category = category_map.get(category, PatternCategory.SYNTAX)
        else:
            pattern_category = category
        
        # Use passed language_id or default to instance language_id
        language = language_id or self.language_id
        
        # Find patterns matching criteria
        for name, pattern in self.patterns.items():
            # Check if pattern matches category
            pattern_category_attr = getattr(pattern, 'category', None)
            if pattern_category_attr != pattern_category:
                continue
                
            # Check if pattern matches purpose
            if purpose:
                pattern_purpose = getattr(pattern, 'purpose', None)
                if pattern_purpose != purpose:
                    continue
            
            # Check if pattern matches language
            pattern_language = getattr(pattern, 'language_id', None)
            if pattern_language and pattern_language != language:
                continue
                
            # Check if pattern matches parser type
            if parser_type:
                pattern_parser_type = getattr(pattern, 'parser_type', None)
                if pattern_parser_type and pattern_parser_type != parser_type:
                    continue
            
            # Add pattern to results
            result.append({
                "name": name,
                "pattern": pattern.pattern if hasattr(pattern, 'pattern') else None,
                "tree_sitter_query": pattern.tree_sitter_query if hasattr(pattern, 'tree_sitter_query') else None,
                "category": getattr(pattern, 'category', PatternCategory.SYNTAX).value 
                    if hasattr(getattr(pattern, 'category', None), 'value') else str(getattr(pattern, 'category', "")),
                "purpose": getattr(pattern, 'purpose', PatternPurpose.UNDERSTANDING).value
                    if hasattr(getattr(pattern, 'purpose', None), 'value') else str(getattr(pattern, 'purpose', "")),
                "language_id": getattr(pattern, 'language_id', language)
            })
        
        return result
    
    @handle_async_errors(error_types=ProcessingError)
    async def get_patterns_for_block_type(
        self,
        block_type: Any,  # Actual type is BlockType but avoid circular import
        language_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get patterns for a specific block type.
        
        Args:
            block_type: Block type to get patterns for
            language_id: Language filter (optional)
            
        Returns:
            List[Dict[str, Any]]: List of patterns for the block type
        """
        # Convert block_type to string if it has a value attribute
        block_type_str = block_type.value if hasattr(block_type, 'value') else str(block_type)
        
        # Use passed language_id or default to instance language_id
        language = language_id or self.language_id
        
        # Find patterns matching block type
        result = []
        for name, pattern in self.patterns.items():
            # Check if pattern is for the block type
            pattern_block_type = getattr(pattern, 'block_type', None)
            if pattern_block_type:
                pattern_block_type_str = pattern_block_type.value if hasattr(pattern_block_type, 'value') else str(pattern_block_type)
                if pattern_block_type_str != block_type_str:
                    continue
            else:
                # Skip if pattern doesn't have a block type
                continue
                
            # Check if pattern matches language
            pattern_language = getattr(pattern, 'language_id', None)
            if pattern_language and pattern_language != language:
                continue
                
            # Add pattern to results
            result.append({
                "name": name,
                "pattern": pattern.pattern if hasattr(pattern, 'pattern') else None,
                "tree_sitter_query": pattern.tree_sitter_query if hasattr(pattern, 'tree_sitter_query') else None,
                "block_type": block_type_str,
                "category": getattr(pattern, 'category', PatternCategory.SYNTAX).value 
                    if hasattr(getattr(pattern, 'category', None), 'value') else str(getattr(pattern, 'category', "")),
                "language_id": getattr(pattern, 'language_id', language)
            })
            
        return result

# Global instance cache
_processor_instances: Dict[str, PatternProcessor] = {}

async def get_pattern_processor(language_id: str) -> Optional[PatternProcessor]:
    """Get a pattern processor instance.
    
    Args:
        language_id: The language to get processor for
        
    Returns:
        Optional[PatternProcessor]: The processor instance or None if initialization fails
    """
    if language_id not in _processor_instances:
        processor = PatternProcessor(language_id)
        if await processor.initialize():
            _processor_instances[language_id] = processor
        else:
            return None
    return _processor_instances[language_id]

# Export commonly used functions
__all__ = [
    'get_pattern_processor',
    'validate_all_patterns',
    'report_validation_results'
] 