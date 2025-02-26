"""Repository learning rule configuration.

This module defines the rules and configurations for repository pattern learning,
including thresholds, extraction policies, and graph analysis parameters.
"""

from typing import Dict, List, Any
from enum import Enum
import os

class PatternType(str, Enum):
    """Types of patterns that can be extracted from repositories."""
    CODE_STRUCTURE = "code_structure"
    CODE_NAMING = "code_naming"
    ERROR_HANDLING = "error_handling"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    COMPONENT_DEPENDENCY = "component_dependency"


class ExtractionPolicy(str, Enum):
    """Policies for extracting patterns from repositories."""
    STRICT = "strict"       # Only extract patterns with high confidence
    BALANCED = "balanced"   # Extract patterns with moderate confidence
    INCLUSIVE = "inclusive" # Extract all potential patterns


# Default thresholds for pattern extraction
DEFAULT_THRESHOLDS = {
    "similarity_cutoff": 0.5,      # Minimum similarity score for pattern matching
    "code_pattern_minimum": 3,     # Minimum occurrences to consider a code pattern
    "confidence_threshold": 0.7,   # Minimum confidence for pattern extraction
    "pattern_cluster_size": 2,     # Minimum size for a pattern cluster
}

# Graph algorithm configurations
GRAPH_ALGORITHMS = {
    "similarity": {
        "algorithm": "gds.nodeSimilarity.stream",
        "config": {
            "topK": 10,
            "similarityCutoff": 0.5
        }
    },
    "clustering": {
        "algorithm": "gds.louvain.stream",
        "config": {
            "relationshipWeightProperty": "confidence"
        }
    },
    "centrality": {
        "algorithm": "gds.pageRank.stream",
        "config": {
            "maxIterations": 20,
            "dampingFactor": 0.85
        }
    }
}

# Extraction policies by pattern type
EXTRACTION_POLICIES = {
    PatternType.CODE_STRUCTURE: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 3,
            "confidence": 0.7
        }
    },
    PatternType.CODE_NAMING: {
        "policy": ExtractionPolicy.STRICT,
        "thresholds": {
            "min_occurrences": 5,
            "confidence": 0.8
        }
    },
    PatternType.ERROR_HANDLING: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 2,
            "confidence": 0.7
        }
    },
    PatternType.DOCUMENTATION: {
        "policy": ExtractionPolicy.INCLUSIVE,
        "thresholds": {
            "min_occurrences": 1,
            "confidence": 0.6
        }
    },
    PatternType.ARCHITECTURE: {
        "policy": ExtractionPolicy.STRICT,
        "thresholds": {
            "min_occurrences": 1,
            "confidence": 0.9
        }
    },
    PatternType.COMPONENT_DEPENDENCY: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 2,
            "confidence": 0.7
        }
    }
}

# Language-specific pattern extraction rules
LANGUAGE_RULES = {
    "python": {
        "naming_conventions": {
            "class": r"^[A-Z][a-zA-Z0-9]*$",
            "function": r"^[a-z][a-zA-Z0-9_]*$",
            "variable": r"^[a-z][a-zA-Z0-9_]*$"
        },
        "error_patterns": ["try", "except", "finally", "raise"],
        "imports": ["import", "from"]
    },
    "javascript": {
        "naming_conventions": {
            "class": r"^[A-Z][a-zA-Z0-9]*$",
            "function": r"^[a-z][a-zA-Z0-9_]*$",
            "variable": r"^[a-z][a-zA-Z0-9_]*$"
        },
        "error_patterns": ["try", "catch", "finally", "throw"],
        "imports": ["import", "require"]
    },
    "typescript": {
        "naming_conventions": {
            "interface": r"^I[A-Z][a-zA-Z0-9]*$",
            "class": r"^[A-Z][a-zA-Z0-9]*$",
            "function": r"^[a-z][a-zA-Z0-9_]*$",
            "variable": r"^[a-z][a-zA-Z0-9_]*$"
        },
        "error_patterns": ["try", "catch", "finally", "throw"],
        "imports": ["import", "require"]
    },
    "java": {
        "naming_conventions": {
            "class": r"^[A-Z][a-zA-Z0-9]*$",
            "method": r"^[a-z][a-zA-Z0-9_]*$",
            "variable": r"^[a-z][a-zA-Z0-9_]*$",
            "constant": r"^[A-Z][A-Z0-9_]*$"
        },
        "error_patterns": ["try", "catch", "finally", "throw"],
        "imports": ["import"]
    },
    "default": {
        "naming_conventions": {
            "class": r"^[A-Z][a-zA-Z0-9]*$",
            "function": r"^[a-z][a-zA-Z0-9_]*$",
            "variable": r"^[a-z][a-zA-Z0-9_]*$"
        },
        "error_patterns": ["try", "catch", "except", "finally", "throw", "raise"],
        "imports": ["import", "require", "from", "using", "include"]
    }
}

# Documentation pattern rules
DOC_PATTERN_RULES = {
    "markdown": {
        "heading_pattern": r"^#+\s+(.+)$",
        "code_block_pattern": r"```[\w]*\n[\s\S]*?\n```",
        "link_pattern": r"\[([^\]]+)\]\(([^)]+)\)",
        "list_pattern": r"^\s*[-*+]\s+(.+)$"
    },
    "rst": {
        "heading_pattern": r"^[=\-`~:#'\"^_*+<>]{3,}\s*$",
        "code_block_pattern": r"::\n\n[\s\S]*?(?=\S)",
        "link_pattern": r"`([^`]+)`_",
        "list_pattern": r"^\s*[-*+]\s+(.+)$"
    },
    "javadoc": {
        "tag_pattern": r"@(\w+)\s+(.+)$",
        "param_pattern": r"@param\s+(\w+)\s+(.+)$",
        "return_pattern": r"@return\s+(.+)$",
        "throws_pattern": r"@throws\s+(\w+)\s+(.+)$"
    },
    "default": {
        "heading_pattern": r"^[#=\-*]+\s*(.+?)\s*[#=\-*]*$",
        "code_block_pattern": r"```[\w]*\n[\s\S]*?\n```|::\n\n[\s\S]*?(?=\S)",
        "link_pattern": r"\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`_",
        "list_pattern": r"^\s*[-*+]\s+(.+)$"
    }
}

# Return a copy of the default thresholds
def get_default_thresholds() -> Dict[str, Any]:
    """Get a copy of the default threshold settings."""
    return DEFAULT_THRESHOLDS.copy()

# Get extraction policy for a specific pattern type
def get_policy_for_pattern(pattern_type: PatternType) -> Dict[str, Any]:
    """Get the extraction policy for a specific pattern type."""
    return EXTRACTION_POLICIES.get(pattern_type, 
                                 EXTRACTION_POLICIES.get(PatternType.CODE_STRUCTURE))

# Get algorithm configuration for a specific algorithm
def get_algorithm_config(algorithm_type: str) -> Dict[str, Any]:
    """Get the configuration for a graph algorithm."""
    return GRAPH_ALGORITHMS.get(algorithm_type, GRAPH_ALGORITHMS["similarity"])

# Get language-specific rules
def get_language_rules(language: str) -> Dict[str, Any]:
    """Get rules for a specific programming language."""
    return LANGUAGE_RULES.get(language.lower(), LANGUAGE_RULES["default"])

# Get documentation pattern rules
def get_doc_pattern_rules(doc_type: str) -> Dict[str, Any]:
    """Get rules for a specific documentation type."""
    return DOC_PATTERN_RULES.get(doc_type.lower(), DOC_PATTERN_RULES["default"]) 