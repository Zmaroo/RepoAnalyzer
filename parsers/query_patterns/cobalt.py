"""Query patterns for the Cobalt programming language."""

from typing import Dict, Any, List, Match
from dataclasses import dataclass
from parsers.types import FileType, QueryPattern, PatternCategory
import re

def extract_function(match: Match) -> Dict[str, Any]:
    """Extract function information."""
    return {
        "name": match.group(1),
        "parameters": match.group(2),
        "return_type": match.group(3) if match.lastindex >= 3 else None,
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

def extract_class(match: Match) -> Dict[str, Any]:
    """Extract class information."""
    return {
        "type": "class",
        "name": match.group(1),
        "parent": match.group(2),
        "line_number": match.string.count('\n', 0, match.start()) + 1
    }

COBALT_PATTERNS = {
    PatternCategory.SYNTAX: {
        "function": QueryPattern(
            pattern=r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)(?:\s*->\s*([a-zA-Z_][a-zA-Z0-9_<>]*))?\s*{',
            extract=extract_function,
            description="Matches Cobalt function declarations",
            examples=["function calculate(x, y) -> int {"]
        ),
        "class": QueryPattern(
            pattern=r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:extends\s+([a-zA-Z_][a-zA-Z0-9_]*))?(?:implements\s+((?:[a-zA-Z_][a-zA-Z0-9_]*(?:,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)))?\s*{',
            extract=lambda m: {
                "name": m.group(1),
                "extends": m.group(2) if m.lastindex >= 2 else None,
                "implements": [i.strip() for i in m.group(3).split(',')] if m.lastindex >= 3 and m.group(3) else [],
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt class declarations",
            examples=["class User extends Entity {"]
        ),
        "variable": QueryPattern(
            pattern=r'(?:let|const|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*([a-zA-Z_][a-zA-Z0-9_<>]*))?(?:\s*=\s*(.+))?;',
            extract=lambda m: {
                "name": m.group(1),
                "type": m.group(2) if m.lastindex >= 2 else None,
                "init_value": m.group(3) if m.lastindex >= 3 else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt variable declarations",
            examples=["let count: int = 0;"]
        ),
        "if_statement": QueryPattern(
            pattern=r'if\s*\((.+?)\)\s*{',
            extract=lambda m: {
                "condition": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt if statements",
            examples=["if (x > 0) {"]
        )
    },
    
    PatternCategory.STRUCTURE: {
        "namespace": QueryPattern(
            pattern=r'namespace\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{',
            extract=lambda m: {
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt namespace declarations",
            examples=["namespace Utils {"]
        ),
        "import": QueryPattern(
            pattern=r'import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*(?:as\s+([a-zA-Z_][a-zA-Z0-9_]*))?;',
            extract=lambda m: {
                "path": m.group(1),
                "alias": m.group(2) if m.lastindex >= 2 else None,
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt import statements",
            examples=["import Math.random;"]
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "docstring": QueryPattern(
            pattern=r'///\s*(.+)',
            extract=lambda m: {
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt doc comments",
            examples=["/// This is a doc comment"]
        ),
        "comment": QueryPattern(
            pattern=r'//\s*(.+)',
            extract=lambda m: {
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt line comments",
            examples=["// This is a comment"]
        )
    },
    
    PatternCategory.SEMANTICS: {
        "type": QueryPattern(
            pattern=r'type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+);',
            extract=lambda m: {
                "name": m.group(1),
                "definition": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt type definitions",
            examples=["type Point = {x: int, y: int};"]
        ),
        "enum": QueryPattern(
            pattern=r'enum\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*{',
            extract=lambda m: {
                "name": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1
            },
            description="Matches Cobalt enum declarations",
            examples=["enum Color {"]
        )
    }
}

# Add patterns for repository learning
COBALT_PATTERNS_FOR_LEARNING = {
    "code_structure": {
        "function_pattern": QueryPattern(
            pattern=r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)(?:\s*->\s*([a-zA-Z_][a-zA-Z0-9_<>]*))?\s*{[\s\S]*?}',
            extract=lambda m: {
                "type": "function_pattern",
                "name": m.group(1),
                "parameters": m.group(2),
                "return_type": m.group(3) if m.lastindex >= 3 else None,
                "has_typed_signature": m.lastindex >= 3 and m.group(3) is not None
            },
            description="Matches complete Cobalt function definitions",
            examples=["function calculate(x: int, y: int) -> int { return x + y; }"]
        ),
        "class_pattern": QueryPattern(
            pattern=r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:extends\s+([a-zA-Z_][a-zA-Z0-9_]*))?(?:implements\s+((?:[a-zA-Z_][a-zA-Z0-9_]*(?:,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)))?\s*{[\s\S]*?}',
            extract=lambda m: {
                "type": "class_pattern",
                "name": m.group(1),
                "extends": m.group(2) if m.lastindex >= 2 and m.group(2) else None,
                "implements": [i.strip() for i in m.group(3).split(',')] if m.lastindex >= 3 and m.group(3) else [],
                "uses_inheritance": m.lastindex >= 2 and m.group(2) is not None
            },
            description="Matches complete Cobalt class definitions",
            examples=["class User extends Entity { let id: int; }"]
        )
    },
    "error_handling": {
        "try_catch_pattern": QueryPattern(
            pattern=r'try\s*{[\s\S]*?}\s*catch\s*\(([a-zA-Z_][a-zA-Z0-9_]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\)\s*{[\s\S]*?}',
            extract=lambda m: {
                "type": "try_catch_pattern",
                "error_type": m.group(1),
                "error_var": m.group(2),
                "has_error_handling": True
            },
            description="Matches Cobalt try-catch blocks",
            examples=["try { doSomething(); } catch (Error e) { handleError(e); }"]
        ),
        "throw_pattern": QueryPattern(
            pattern=r'throw\s+new\s+([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\);',
            extract=lambda m: {
                "type": "throw_pattern",
                "error_type": m.group(1),
                "error_args": m.group(2),
                "has_explicit_throws": True
            },
            description="Matches Cobalt throw statements",
            examples=["throw new ValueError(\"Invalid input\");"]
        )
    },
    "naming_conventions": {
        "camel_case_function": QueryPattern(
            pattern=r'function\s+([a-z][a-zA-Z0-9]*)\s*\(',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "camel_case",
                "category": "function",
                "name": m.group(1),
                "follows_convention": bool(re.match(r'^[a-z][a-zA-Z0-9]*$', m.group(1)))
            },
            description="Matches camelCase function naming convention",
            examples=["function calculateTotal(items) {"]
        ),
        "pascal_case_class": QueryPattern(
            pattern=r'class\s+([A-Z][a-zA-Z0-9]*)\s*',
            extract=lambda m: {
                "type": "naming_convention",
                "convention": "pascal_case",
                "category": "class",
                "name": m.group(1),
                "follows_convention": bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', m.group(1)))
            },
            description="Matches PascalCase class naming convention",
            examples=["class UserAccount {"]
        )
    }
}

# Add the repository learning patterns to the main patterns
COBALT_PATTERNS['REPOSITORY_LEARNING'] = COBALT_PATTERNS_FOR_LEARNING

# Function to extract patterns for repository learning
def extract_cobalt_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Cobalt content for repository learning."""
    patterns = []
    
    # Process code structure patterns
    for pattern_name, pattern in COBALT_PATTERNS_FOR_LEARNING["code_structure"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "code_structure"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.8
            })
    
    # Process error handling patterns
    for pattern_name, pattern in COBALT_PATTERNS_FOR_LEARNING["error_handling"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "error_handling"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.75
            })
    
    # Process naming convention patterns
    for pattern_name, pattern in COBALT_PATTERNS_FOR_LEARNING["naming_conventions"].items():
        for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.DOTALL):
            pattern_data = pattern.extract(match)
            patterns.append({
                "name": pattern_name,
                "type": pattern_data.get("type", "naming_convention"),
                "content": match.group(0),
                "metadata": pattern_data,
                "confidence": 0.7
            })
            
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        "can_contain": ["variable", "comment", "docstring"],
        "can_be_contained_by": ["class", "namespace"]
    },
    "class": {
        "can_contain": ["function", "variable", "comment", "docstring"],
        "can_be_contained_by": ["namespace"]
    },
    "namespace": {
        "can_contain": ["class", "function", "variable", "comment"],
        "can_be_contained_by": ["namespace"]
    }
} 