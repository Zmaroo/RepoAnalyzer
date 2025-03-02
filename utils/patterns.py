"""
Pattern utilities for the RepoAnalyzer project.

This module provides functions for managing code patterns across repositories.
"""

import asyncio
from typing import Dict, List, Tuple, Any
from utils.logger import log

@handle_async_errors(error_types=(Exception,))
async def get_common_patterns(limit: int = 50) -> Dict[str, str]:
    """
    Get most commonly used patterns.
    
    Args:
        limit: Maximum number of patterns to return
        
    Returns:
        Dict mapping pattern names to pattern definitions
    """
    # This would normally query from a database or analytics service
    # For now, return sample patterns
    return {
        "function_definition": r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
        "class_definition": r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(|:)",
        "import_statement": r"import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)",
        "from_import": r"from\s+([a-zA-Z_][a-zA-Z0-9_\.]*)\s+import",
        "variable_assignment": r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"
    }
@handle_async_errors(error_types=(Exception,))

async def get_language_patterns(language: str) -> Dict[str, str]:
    """
    Get patterns specific to a programming language.
    
    Args:
        language: Programming language to get patterns for
        
    Returns:
        Dict mapping pattern names to pattern definitions
    """
    patterns = {
        "python": {
            "decorator": r"@([a-zA-Z_][a-zA-Z0-9_\.]*)",
            "with_statement": r"with\s+([^:]+):",
            "async_function": r"async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            "f_string": r"f['\"]([^'\"]*)['\"]",
            "list_comprehension": r"\[\s*([^\]\[]+)\s+for\s+"
        },
        "javascript": {
            "arrow_function": r"const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\([^)]*\)\s*=>",
            "jsx_component": r"<([A-Z][a-zA-Z0-9_]*)",
            "destructuring": r"const\s*\{\s*([^}]+)\s*\}\s*=",
            "export_statement": r"export\s+(default\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
            "import_statement": r"import\s+\{\s*([^}]+)\s*\}\s+from"
        }
    }
    
    if language.lower() not in patterns:
        log(f"No patterns available for language '{language}'", level="warning")
        return {}
        
@handle_async_errors(error_types=(Exception,))
    return patterns[language.lower()]

async def get_pattern_complexity(min_complexity: float = 0.0) -> Dict[str, Tuple[str, float]]:
    """
    Get patterns with their complexity rating.
    
    Args:
        min_complexity: Minimum complexity threshold
        
    Returns:
        Dict mapping pattern names to tuples of (pattern, complexity)
    """
    # This would normally calculate or retrieve complexity ratings
    # For now, provide sample data
    patterns_with_complexity = {
        "simple_function": (r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", 0.3),
        "simple_class": (r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:", 0.4),
        "nested_function": (r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\):[^def]*def", 0.7),
        "complex_decorator": (r"@([a-zA-Z_][a-zA-Z0-9_\.]*)\([^)]*\)", 0.8),
        "complex_regex": (r"re\.compile\(r['\"]([^'\"]+)['\"]", 0.9)
    }
    
    # Filter by complexity if needed
    if min_complexity > 0:
        return {
            name: (pattern, complexity)
            for name, (pattern, complexity) in patterns_with_complexity.items()
            if complexity >= min_complexity
        }
@handle_async_errors(error_types=(Exception,))
    
    return patterns_with_complexity

async def get_commonly_accessed_files(limit: int = 20) -> List[str]:
    """
    Get the most commonly accessed files in the repositories.
    
    Args:
        limit: Maximum number of files to return
        
    Returns:
        List of file paths
    """
    # This would normally query from analytics or database
    # For now, return sample files
    return [
        "main.py",
        "utils/cache.py",
        "utils/patterns.py",
        "db/transaction.py",
        "indexer/file_processor.py"
    ] 