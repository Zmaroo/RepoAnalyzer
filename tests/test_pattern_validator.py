#!/usr/bin/env python3
"""
Unit tests for the pattern validator module.
Tests the validation functionality for pattern definitions.
"""

import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from parsers.pattern_validator import (
    PatternValidator, 
    validate_all_patterns, 
    report_validation_results,
    PatternValidationError
)
from parsers.types import PatternDefinition, QueryPattern, PatternCategory
from typing import List

# Test pattern definitions
@dataclass
class TestPatternDefinition(PatternDefinition):
    """Test pattern definition class."""
    pattern: str
    extract: callable = None
    description: str = None

@dataclass
class TestQueryPattern:
    """Test query pattern class for testing only."""
    pattern: str
    query: str
    extract: callable = None
    description: str = None
    examples: List[str] = field(default_factory=list)
    category: str = None
    language_id: str = None
    name: str = None
    definition: PatternDefinition = None

class TestPatternValidator:
    """Tests for the PatternValidator class."""
    
    def test_validate_pattern_definition_valid(self):
        """Test validation of a valid pattern definition."""
        # Create a valid pattern
        pattern_name = "valid_pattern"
        definition = TestPatternDefinition(
            pattern=r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            extract=lambda x: x,
            description="Valid pattern"
        )
        
        errors = PatternValidator.validate_pattern_definition(pattern_name, definition)
        assert not errors, f"Expected no errors but got: {errors}"
    
    def test_validate_pattern_definition_missing_pattern(self):
        """Test validation of a pattern definition with missing pattern."""
        # Create a pattern with missing pattern string
        pattern_name = "invalid_pattern"
        definition = TestPatternDefinition(
            pattern="",
            extract=lambda x: x,
            description="Invalid pattern"
        )
        
        errors = PatternValidator.validate_pattern_definition(pattern_name, definition)
        assert errors
        assert any("missing a pattern string" in error for error in errors)
    
    def test_validate_pattern_definition_invalid_regex(self):
        """Test validation of a pattern definition with invalid regex."""
        # Create a pattern with invalid regex
        pattern_name = "invalid_regex"
        definition = TestPatternDefinition(
            pattern=r"def[",  # Unclosed character class
            extract=lambda x: x,
            description="Invalid regex pattern"
        )
        
        errors = PatternValidator.validate_pattern_definition(pattern_name, definition)
        assert errors
        assert any("invalid regex" in error for error in errors)
    
    def test_validate_pattern_definition_non_callable_extract(self):
        """Test validation of a pattern definition with non-callable extract."""
        # Create a pattern with non-callable extract
        pattern_name = "non_callable_extract"
        definition = TestPatternDefinition(
            pattern=r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            extract="not_a_function",  # Should be callable
            description="Pattern with non-callable extract"
        )
        
        errors = PatternValidator.validate_pattern_definition(pattern_name, definition)
        assert errors
        assert any("non-callable extract method" in error for error in errors)
    
    def test_validate_query_pattern_valid(self):
        """Test validation of a valid query pattern."""
        # Create a valid query pattern
        pattern_name = "valid_query"
        definition = TestQueryPattern(
            pattern="(function_definition) @function",
            query="(function_definition) @function",
            extract=lambda x: x,
            description="Valid query pattern"
        )
        
        errors = PatternValidator.validate_query_pattern(pattern_name, definition)
        assert not errors, f"Expected no errors but got: {errors}"
    
    def test_validate_query_pattern_missing_query(self):
        """Test validation of a query pattern with missing query."""
        # Create a query pattern with missing query
        pattern_name = "invalid_query"
        definition = TestQueryPattern(
            pattern="(function_definition) @function",
            query="",
            extract=lambda x: x,
            description="Invalid query pattern"
        )
        
        errors = PatternValidator.validate_query_pattern(pattern_name, definition)
        assert errors
        assert any("missing a query string" in error for error in errors)
    
    def test_validate_language_patterns(self):
        """Test validation of all patterns for a language."""
        # Create a mix of valid and invalid patterns
        patterns = {
            "valid_pattern": TestPatternDefinition(
                pattern="(function_definition) @function",
                extract=lambda x: x
            ),
            "valid_query": TestQueryPattern(
                pattern="(function_definition) @function",
                query="(function_definition) @function",
                extract=lambda x: x
            )
        }
        
        validation_results = PatternValidator.validate_language_patterns("python", patterns)
        assert "valid_pattern" not in validation_results
        assert "valid_query" not in validation_results
    
    def test_validate_pattern_naming(self):
        """Test validation of pattern naming conventions."""
        # Test valid name
        errors = PatternValidator.validate_pattern_naming("valid_pattern_name")
        assert not errors
        
        # Test empty name
        errors = PatternValidator.validate_pattern_naming("")
        assert errors
        assert any("cannot be empty" in error for error in errors)
        
        # Test name with spaces
        errors = PatternValidator.validate_pattern_naming("invalid pattern name")
        assert errors
        assert any("contains spaces" in error for error in errors)
        
        # Test name not in snake_case
        errors = PatternValidator.validate_pattern_naming("InvalidPatternName")
        assert errors
        assert any("should use snake_case" in error for error in errors)
    
    def test_check_duplicate_patterns(self):
        """Test checking for duplicate patterns."""
        # Create patterns with duplicate regex
        patterns = {
            "function_def": TestPatternDefinition(
                pattern=r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
            ),
            "function_definition": TestPatternDefinition(
                pattern=r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("  # Same as above
            ),
            "unique_pattern": TestPatternDefinition(
                pattern=r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:"
            )
        }
        
        warnings = PatternValidator.check_duplicate_patterns(patterns)
        assert warnings
        assert any("function_def" in warning and "function_definition" in warning for warning in warnings)


class TestPatternValidationFunctions:
    """Tests for the pattern validation helper functions."""
    
    def test_validate_all_patterns(self):
        """Test validation across multiple languages."""
        # Create patterns for multiple languages
        patterns_by_language = {
            "python": {
                "valid_pattern": TestPatternDefinition(
                    pattern="(function_definition) @function",
                    extract=lambda x: x
                ),
                "invalid_pattern": TestPatternDefinition(
                    pattern="",
                    extract=lambda x: x
                )
            },
            "javascript": {
                "valid_pattern": TestPatternDefinition(
                    pattern=r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
                    extract=lambda x: x
                )
            }
        }
        
        validation_results = validate_all_patterns(patterns_by_language)
        assert "python" in validation_results
        assert "javascript" not in validation_results
        assert "invalid_pattern" in validation_results["python"]
    
    def test_report_validation_results_with_errors(self):
        """Test reporting validation results with errors."""
        # Create validation results with errors
        validation_results = {
            "python": {
                "invalid_pattern": ["Pattern 'invalid_pattern' is missing a pattern string"]
            }
        }
        
        report = report_validation_results(validation_results)
        assert "Pattern Validation Results" in report
        assert "Found 1 errors across 1 languages" in report
        assert "Language: python (1 errors)" in report
        assert "Pattern 'invalid_pattern'" in report
    
    def test_report_validation_results_no_errors(self):
        """Test reporting validation results with no errors."""
        # Create empty validation results (no errors)
        validation_results = {}
        
        report = report_validation_results(validation_results)
        assert "All patterns passed validation" in report

if __name__ == "__main__":
    pytest.main() 