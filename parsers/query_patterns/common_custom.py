"""Common regex query patterns for custom parsers.

This module contains regex patterns for custom parsers that can be used across
different languages. These patterns focus on regex-based extraction and are tailored
for custom parsers, without any tree-sitter dependencies.

The module provides:
- A catalog of regex patterns organized by category (syntax, documentation, etc.)
- Utility functions for matching patterns against source code
- Context classes for pattern execution and metrics tracking
- A pattern learner for improving regex patterns based on project analysis

Examples:
    # Match a specific pattern against source code
    matches = await match_regex_pattern(
        pattern=r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)",
        content=source_code,
        extract_func=lambda m: {"name": m.group(1), "params": m.group(2)}
    )
    
    # Match all patterns from a category against source code
    category_patterns = PATTERN_CATEGORIES[PatternCategory.SYNTAX]
    all_matches = await match_custom_patterns(
        patterns=category_patterns,
        content=source_code,
        language_id="python"
    )
    
    # Use the pattern learner to improve patterns
    learner = CommonPatternLearner()
    await learner.initialize()
    learned_patterns = await learner.learn_from_project("/path/to/project")
"""

import time
import re
from typing import Dict, List, Optional, Any, Union, Callable

from parsers.base_parser import BaseParser
from parsers.types import (
    PatternCategory,
    PatternPurpose,
    ParserType,
    ComponentStatus,
    FileType,
)
from parsers.query_patterns.enhanced_patterns import (
    TreeSitterCrossProjectPatternLearner,
    TreeSitterAdaptivePattern,
    PatternPerformanceMetrics,
    PatternValidationResult,
    PatternContext as CustomPatternContext
)
from utils.logger import log
from utils.health_monitor import global_health_monitor

# Define common pattern categories
PATTERN_CATEGORIES = {
    PatternCategory.SYNTAX: {
        "function_definition": {
            "regex": r"(?:def|function)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)",
            "extract": lambda match: {
                "name": match.group(1),
                "params": match.group(2)
            }
        },
        "class_definition": {
            "regex": r"(?:class)\s+([a-zA-Z0-9_]+)(?:\s*(?:extends|implements)\s+([a-zA-Z0-9_., ]+))?",
            "extract": lambda match: {
                "name": match.group(1), 
                "extends": match.group(2) if match.lastindex >= 2 else None
            }
        },
        "import_statement": {
            "regex": r"(?:import|require|using|include)\s+(.*?)(?:;|$)",
            "extract": lambda match: {"module": match.group(1).strip()}
        },
        "variable_declaration": {
            "regex": r"(?:var|let|const|int|string|float|double|bool)\s+([a-zA-Z0-9_]+)\s*=\s*([^;]*)",
            "extract": lambda match: {
                "name": match.group(1),
                "value": match.group(2)
            }
        },
        "conditional_statement": {
            "regex": r"(if|elif|else if|switch)\s*\(([^)]*)\)",
            "extract": lambda match: {"condition": match.group(2)}
        },
        "loop_statement": {
            "regex": r"(for|while|do while|foreach)\s*\(([^)]*)\)",
            "extract": lambda match: {"condition": match.group(2)}
        }
    },
    PatternCategory.DOCUMENTATION: {
        "comment_block": {
            "regex": r"(?:/\*\*|\*\*\*|###|\"\"\")([\s\S]*?)(?:\*/|\"\"\"|###)",
            "extract": lambda match: {"content": match.group(1).strip()}
        },
        "line_comment": {
            "regex": r"(?://|#|--|;)(.*)$",
            "extract": lambda match: {"content": match.group(1).strip()}
        },
        "todo_comment": {
            "regex": r"(?://|#|--|;)\s*TODO:?(.*)$",
            "extract": lambda match: {"content": match.group(1).strip()}
        },
        "fixme_comment": {
            "regex": r"(?://|#|--|;)\s*FIXME:?(.*)$",
            "extract": lambda match: {"content": match.group(1).strip()}
        },
        "docstring": {
            "regex": r'"""([\s\S]*?)"""',
            "extract": lambda match: {"content": match.group(1).strip()}
        }
    },
    PatternCategory.DEPENDENCIES: {
        "dependency_declaration": {
            "regex": r'(?:require|import|include|using)\s+([\'"]?)([^\'"\n]+)\1',
            "extract": lambda match: {"name": match.group(2).strip()}
        },
        "package_declaration": {
            "regex": r'package\s+([a-zA-Z0-9_.]+)',
            "extract": lambda match: {"name": match.group(1).strip()}
        },
        "version_specification": {
            "regex": r'v?(\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?)',
            "extract": lambda match: {"version": match.group(1)}
        }
    },
    PatternCategory.BEST_PRACTICES: {
        "magic_number": {
            "regex": r'(?<![a-zA-Z0-9_])([-+]?\d{4,}|0x[0-9a-fA-F]{3,})(?![a-zA-Z0-9_])',
            "extract": lambda match: {"value": match.group(1)}
        },
        "hardcoded_path": {
            "regex": r'(?:[\'"])((?:/|\\|\w:)[\w\/\\.-]+)(?:[\'"])',
            "extract": lambda match: {"path": match.group(1)}
        },
        "exposed_credential": {
            "regex": r'(?:password|api_?key|secret|token|auth)\s*(?:=|:)\s*[\'"]([^\'"]{8,})[\'"]',
            "extract": lambda match: {"credential_type": match.group(0).split('=')[0].strip()}
        }
    },
    PatternCategory.COMMON_ISSUES: {
        "debug_statement": {
            "regex": r'(?:console\.log|print|debug|alert)\s*\(([^)]*)\)',
            "extract": lambda match: {"content": match.group(1).strip()}
        },
        "empty_block": {
            "regex": r'(?:if|for|while|switch|function)[^{]*\{\s*\}',
            "extract": lambda match: {"content": match.group(0).strip()}
        },
        "unreachable_code": {
            "regex": r'(?:return|break|continue|exit|die);?\s*(?![\s}]*(?://|/\*))([^;{}]*?);',
            "extract": lambda match: {"content": match.group(1).strip() if match.lastindex >= 1 else ""}
        }
    }
}

# Compile the common patterns from all categories
COMMON_PATTERNS = {}
for category, patterns in PATTERN_CATEGORIES.items():
    COMMON_PATTERNS.update(patterns)

# List of capabilities provided by common patterns
COMMON_CAPABILITIES = [
    "detect_function_definitions",
    "detect_class_definitions",
    "detect_import_statements",
    "detect_variable_declarations",
    "detect_comments_and_documentation",
    "detect_dependency_information",
    "identify_best_practices_violations",
    "identify_common_code_issues"
]

# Mapping of capabilities to patterns
CAPABILITY_PATTERNS = {
    "detect_function_definitions": ["function_definition"],
    "detect_class_definitions": ["class_definition"],
    "detect_import_statements": ["import_statement"],
    "detect_variable_declarations": ["variable_declaration"],
    "detect_comments_and_documentation": ["comment_block", "line_comment", "docstring"],
    "detect_dependency_information": ["dependency_declaration", "package_declaration", "version_specification"],
    "identify_best_practices_violations": ["magic_number", "hardcoded_path", "exposed_credential"],
    "identify_common_code_issues": ["debug_statement", "empty_block", "unreachable_code"]
}

# Common pattern relationships
COMMON_PATTERN_RELATIONSHIPS = {
    "function": [
        {
            "source_pattern": "function",
            "target_pattern": "comment",
            "relationship_type": "COMPLEMENTS",
            "confidence": 0.8,
            "metadata": {"documentation": True}
        }
    ],
    "class": [
        {
            "source_pattern": "class",
            "target_pattern": "method",
            "relationship_type": "CONTAINS",
            "confidence": 0.95,
            "metadata": {"class_members": True}
        },
        {
            "source_pattern": "class",
            "target_pattern": "comment",
            "relationship_type": "COMPLEMENTS",
            "confidence": 0.8,
            "metadata": {"documentation": True}
        }
    ],
    "module": [
        {
            "source_pattern": "module",
            "target_pattern": "import",
            "relationship_type": "CONTAINS",
            "confidence": 0.95,
            "metadata": {"module_system": True}
        },
        {
            "source_pattern": "module",
            "target_pattern": "export",
            "relationship_type": "CONTAINS",
            "confidence": 0.95,
            "metadata": {"module_system": True}
        }
    ]
}

# Performance metrics tracking - simplified for custom regex patterns
PATTERN_METRICS = {}

# Add utility functions for regex pattern matching
async def match_regex_pattern(
    pattern: str,
    content: str,
    extract_func: Optional[Callable] = None,
    context: Optional[CustomPatternContext] = None
) -> List[Dict[str, Any]]:
    """Match regex pattern against content and extract data.
    
    Args:
        pattern: Regex pattern string
        content: Source content to match against
        extract_func: Function to extract data from match objects
        context: Pattern context for metrics and logging
        
    Returns:
        List of extracted pattern matches
    """
    results = []
    start_time = time.time()
    
    try:
        compiled_pattern = re.compile(pattern, re.MULTILINE)
        matches = list(compiled_pattern.finditer(content))
        
        # Extract data from each match
        for match in matches:
            if extract_func:
                extracted_data = extract_func(match)
                if extracted_data:
                    # Add line number information if not present
                    if "line" not in extracted_data:
                        line_num = content[:match.start()].count('\n') + 1
                        extracted_data["line"] = line_num
                    results.append(extracted_data)
            else:
                # Basic extraction
                results.append({
                    "match": match.group(0),
                    "groups": match.groups(),
                    "line": content[:match.start()].count('\n') + 1
                })
        
        # Update metrics if context provided
        if context:
            await context.update_metrics(
                match_count=len(results),
                time_taken=time.time() - start_time
            )
        
        return results
    
    except Exception as e:
        if context:
            await log(f"Error matching pattern {context.pattern_name}: {e}", level="error")
        else:
            await log(f"Error matching regex pattern: {e}", level="error")
        return []

async def match_custom_patterns(
    patterns: Dict[str, Dict],
    content: str,
    language_id: str,
    file_path: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Match multiple custom patterns against content.
    
    Args:
        patterns: Dictionary of pattern name to pattern definition
        content: Source code content to match against
        language_id: Language identifier
        file_path: Optional file path for context
        
    Returns:
        Dictionary of pattern name to list of matches
    """
    results = {}
    
    for pattern_name, pattern_def in patterns.items():
        if "regex" not in pattern_def:
            continue
            
        # Create context for this pattern
        context = CustomPatternContext(
            language_id=language_id,
            pattern_name=pattern_name,
            category=PatternCategory.SYNTAX,  # Default
            purpose=PatternPurpose.UNDERSTANDING,  # Default
            file_path=file_path
        )
        
        # Get regex pattern and extract function
        regex_pattern = pattern_def["regex"]
        extract_func = pattern_def.get("extract")
        
        # Match pattern
        matches = await match_regex_pattern(
            pattern=regex_pattern,
            content=content,
            extract_func=extract_func,
            context=context
        )
        
        if matches:
            results[pattern_name] = matches
    
    return results

class CommonPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Cross-project pattern learner for common regex patterns.
    
    Specializes in learning and improving regex patterns that are
    common across different custom parsers.
    """
    
    def __init__(self):
        """Initialize common pattern learner."""
        super().__init__([])
        self.language_id = "*"  # Applies to all languages
        self.category_patterns = {}
        self._initialized = False
        
        # Track performance per pattern
        self.pattern_performance = {}
    
    async def initialize(self):
        """Initialize pattern learner with common patterns."""
        if self._initialized:
            return
            
        # Get patterns from all categories
        self.category_patterns = {}
        for category in PatternCategory:
            category_patterns = PATTERN_CATEGORIES.get(category, {})
            if category_patterns:
                self.category_patterns[category] = {
                    name: TreeSitterAdaptivePattern(
                        name=name,
                        pattern=pattern.get("regex", ""),
                        category=category,
                        purpose=PatternPurpose.UNDERSTANDING,
                        language_id="*",
                        confidence=0.8,
                        extract=pattern.get("extract"),
                        regex_pattern=pattern.get("regex", "")
                    )
                    for name, pattern in category_patterns.items()
                    if "regex" in pattern
                }
                
                # Add patterns to the learner
                self.patterns.extend(self.category_patterns[category].values())
        
        await super().initialize()
        self._initialized = True
    
    async def _get_parser(self) -> BaseParser:
        """Get an appropriate parser for common patterns."""
        from parsers.base_parser import BaseParser
        
        # Use a basic custom parser
        parser = await BaseParser.create(
            language_id="*",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        return parser
    
    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn common patterns from a project.
        
        Args:
            project_path: Path to project to learn from
            
        Returns:
            List of learned patterns with their metadata
        """
        if not self._initialized:
            await self.initialize()
            
        # Get file contents
        import os
        source_files = []
        
        try:
            for root, _, files in os.walk(project_path):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        
                        # Skip binary files and very large files
                        if os.path.getsize(file_path) > 1024 * 1024:  # 1MB
                            continue
                            
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            source_files.append({
                                "path": file_path,
                                "content": content
                            })
                    except Exception:
                        continue
                        
            # Extract project ID from path
            project_id = os.path.basename(project_path)
            
            # Learn from source files
            await super().learn_from_project(project_id, source_files)
            
            # Extract learned patterns
            patterns = []
            for pattern_name, improvements in self.pattern_improvements.items():
                if improvements:
                    latest = improvements[-1]
                    pattern_def = {
                        "name": pattern_name,
                        "regex": latest.get("improved", ""),
                        "original": latest.get("original", ""),
                        "confidence": 0.9,
                        "improved": True,
                        "language_id": "*"
                    }
                    patterns.append(pattern_def)
            
            return patterns
            
        except Exception as e:
            await log(f"Error learning from project: {e}", level="error")
            return []
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Report pattern learner health
            await global_health_monitor.update_component_status(
                "common_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "patterns_count": len(self.patterns),
                    "improvements": len(self.pattern_improvements)
                }
            )
        except Exception as e:
            await log(f"Error cleaning up common pattern learner: {e}", level="error")

# Initialize pattern learner
common_pattern_learner = CommonPatternLearner()

class CustomPatternContext:
    """Context for custom regex pattern processing.
    
    Provides context information for processing custom regex patterns,
    including metadata about the pattern and its usage.
    """
    
    def __init__(self, 
                 language_id: str,
                 pattern_name: str,
                 category: PatternCategory,
                 purpose: PatternPurpose,
                 file_path: Optional[str] = None,
                 line_number: Optional[int] = None,
                 cache_key: Optional[str] = None,
                 parser_type: ParserType = ParserType.CUSTOM):
        """Initialize pattern context.
        
        Args:
            language_id: Language identifier (e.g., 'python', 'java', 'javascript', etc.)
            pattern_name: Name of the pattern being processed
            category: Category of the pattern (e.g., SYNTAX, SEMANTICS, etc.)
            purpose: Purpose of the pattern (e.g., UNDERSTANDING, ANALYSIS, etc.)
            file_path: Path to the file being processed (optional)
            line_number: Line number in the file (optional)
            cache_key: Key for caching results (optional)
            parser_type: Type of parser (CUSTOM for regex patterns)
        """
        self.language_id = language_id
        self.pattern_name = pattern_name
        self.category = category
        self.purpose = purpose
        self.file_path = file_path
        self.line_number = line_number
        self.cache_key = cache_key or f"{language_id}:{pattern_name}:{file_path or ''}:{line_number or 0}"
        self.parser_type = parser_type
        self.metadata = {}
        self.performance = PatternPerformanceMetrics()
        
    def with_file_path(self, file_path: str) -> 'CustomPatternContext':
        """Create a new context with the specified file path.
    
    Args:
            file_path: Path to the file
        
    Returns:
            New context with updated file path
        """
        context = CustomPatternContext(
            language_id=self.language_id,
            pattern_name=self.pattern_name,
            category=self.category,
            purpose=self.purpose,
            file_path=file_path,
            line_number=self.line_number,
            cache_key=None,  # Will be regenerated
            parser_type=self.parser_type
        )
        context.metadata = self.metadata.copy()
        return context
        
    def with_line_number(self, line_number: int) -> 'CustomPatternContext':
        """Create a new context with the specified line number.
        
        Args:
            line_number: Line number in the file
            
        Returns:
            New context with updated line number
        """
        context = CustomPatternContext(
            language_id=self.language_id,
            pattern_name=self.pattern_name,
            category=self.category,
            purpose=self.purpose,
            file_path=self.file_path,
            line_number=line_number,
            cache_key=None,  # Will be regenerated
            parser_type=self.parser_type
        )
        context.metadata = self.metadata.copy()
        return context
        
    def with_metadata(self, **kwargs) -> 'CustomPatternContext':
        """Create a new context with additional metadata.
    
    Args:
            **kwargs: Metadata key-value pairs
        
    Returns:
            New context with updated metadata
        """
        context = CustomPatternContext(
            language_id=self.language_id,
            pattern_name=self.pattern_name,
            category=self.category,
            purpose=self.purpose,
            file_path=self.file_path,
            line_number=self.line_number,
            cache_key=self.cache_key,
            parser_type=self.parser_type
        )
        context.metadata = self.metadata.copy()
        context.metadata.update(kwargs)
        return context

    async def update_metrics(self, match_count: int, time_taken: float) -> None:
        """Update pattern match metrics.
        
        Args:
            match_count: Number of matches found
            time_taken: Time taken to process the pattern (seconds)
        """
        self.performance.match_time = time_taken
        self.performance.match_count = match_count
        self.performance.cache_hit_rate = 0.0  # No caching for simple regex
        
        try:
            # Report metrics for monitoring
            await global_health_monitor.update_component_status(
                f"pattern_{self.pattern_name}",
                ComponentStatus.HEALTHY,
                details={
                    "language": self.language_id,
                    "matches": match_count,
                    "time_ms": time_taken * 1000,
                    "category": str(self.category),
                    "parser_type": str(self.parser_type)
                }
            )
        except Exception as e:
            await log(f"Error updating metrics: {e}", level="warn")

# Export public interfaces
__all__ = [
    "COMMON_PATTERNS",
    "PATTERN_CATEGORIES",
    "COMMON_CAPABILITIES",
    "CAPABILITY_PATTERNS",
    "COMMON_PATTERN_RELATIONSHIPS",
    "PATTERN_METRICS",
    "CustomPatternContext",
    "CommonPatternLearner",
    "match_regex_pattern",
    "match_custom_patterns",
    "common_pattern_learner"
]

# Initialize pattern learner
common_pattern_learner = CommonPatternLearner()

# Module identification
LANGUAGE = "*" 