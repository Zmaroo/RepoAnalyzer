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
    "embedding_similarity": 0.8,   # Minimum similarity for embedding matches
    "min_pattern_support": 2,      # Minimum number of files supporting a pattern
}

# Graph projection configurations
GRAPH_PROJECTIONS = {
    "code": {
        "name_template": "code-repo-{repo_id}",
        "node_query": """
        MATCH (n) 
        WHERE (n:Code {repo_id: $repo_id}) OR 
              (n:Pattern {repo_id: $repo_id}) OR 
              (n:Repository {id: $repo_id})
        RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties
        """,
        "relationship_query": """
        MATCH (s)-[r]->(t)
        WHERE s.repo_id = $repo_id AND t.repo_id = $repo_id
        AND (
            (s:Code AND t:Code) OR
            (s:Pattern AND t:Code) OR
            (s:Repository AND (t:Code OR t:Pattern))
        )
        RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties
        """
    },
    "pattern": {
        "name_template": "pattern-repo-{repo_id}",
        "node_query": """
        MATCH (n) 
        WHERE (n:Pattern {repo_id: $repo_id}) OR 
              (n:Code {repo_id: $repo_id}) OR 
              (n:Repository {id: $repo_id})
        RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties
        """,
        "relationship_query": """
        MATCH (s)-[r]->(t)
        WHERE (
            (s:Pattern {repo_id: $repo_id} AND t:Code {repo_id: $repo_id} AND type(r) = 'EXTRACTED_FROM') OR
            (s:Repository {id: $repo_id} AND t:Pattern AND type(r) IN ['REFERENCE_PATTERN', 'APPLIED_PATTERN'])
        )
        RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties
        """
    },
    "combined": {
        "name_template": "active-reference-{active_repo_id}-{reference_repo_id}",
        "node_query": """
        MATCH (n) 
        WHERE (
            (n:Code AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id)) OR 
            (n:Pattern AND (n.repo_id = $active_repo_id OR n.repo_id = $reference_repo_id)) OR
            (n:Repository AND n.id IN [$active_repo_id, $reference_repo_id])
        )
        RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties
        """,
        "relationship_query": """
        MATCH (s)-[r]->(t)
        WHERE (
            (s.repo_id IN [$active_repo_id, $reference_repo_id] AND 
             t.repo_id IN [$active_repo_id, $reference_repo_id]) OR
            (s:Repository AND s.id IN [$active_repo_id, $reference_repo_id] AND
             t:Pattern AND t.repo_id IN [$active_repo_id, $reference_repo_id])
        )
        AND (
            (s:Code AND t:Code) OR
            (s:Pattern AND t:Code) OR
            (s:Repository AND (t:Code OR t:Pattern))
        )
        RETURN id(s) AS source, id(t) AS target, type(r) AS type, properties(r) AS properties
        """
    }
}

# Graph algorithm configurations
GRAPH_ALGORITHMS = {
    "similarity": {
        "algorithm": "gds.nodeSimilarity.stream",
        "config": {
            "topK": 10,
            "similarityCutoff": 0.5,
            "relationshipWeightProperty": "confidence"
        }
    },
    "clustering": {
        "algorithm": "gds.louvain.stream",
        "config": {
            "relationshipWeightProperty": "confidence",
            "includeIntermediateCommunities": True
        }
    },
    "centrality": {
        "algorithm": "gds.pageRank.stream",
        "config": {
            "maxIterations": 20,
            "dampingFactor": 0.85,
            "relationshipWeightProperty": "confidence"
        }
    },
    "path_finding": {
        "algorithm": "gds.shortestPath.stream",
        "config": {
            "relationshipWeightProperty": "confidence",
            "path": True
        }
    }
}

# Pattern extraction configurations
PATTERN_EXTRACTION = {
    PatternType.CODE_STRUCTURE: {
        "min_occurrences": 3,
        "confidence_threshold": 0.7,
        "embedding_similarity": 0.8,
        "table": "code_snippets",
        "join_conditions": """
            JOIN code_patterns p ON c.id = p.code_id
            WHERE c.repo_id = $1 AND p.pattern_type = 'code_structure'
        """
    },
    PatternType.DOCUMENTATION: {
        "min_occurrences": 2,
        "confidence_threshold": 0.6,
        "embedding_similarity": 0.7,
        "table": "repo_docs",
        "join_conditions": """
            JOIN repo_doc_relations r ON d.id = r.doc_id
            WHERE r.repo_id = $1 AND d.doc_type = 'pattern'
        """
    },
    PatternType.ARCHITECTURE: {
        "min_occurrences": 1,
        "confidence_threshold": 0.9,
        "table": "code_snippets",
        "join_conditions": """
            WHERE c.repo_id = $1 AND c.file_path LIKE 'architecture/%'
        """
    }
}

# Extraction policies by pattern type
EXTRACTION_POLICIES = {
    PatternType.CODE_STRUCTURE: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 3,
            "confidence": 0.7,
            "embedding_similarity": 0.8
        }
    },
    PatternType.CODE_NAMING: {
        "policy": ExtractionPolicy.STRICT,
        "thresholds": {
            "min_occurrences": 5,
            "confidence": 0.8,
            "embedding_similarity": 0.85
        }
    },
    PatternType.ERROR_HANDLING: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 2,
            "confidence": 0.7,
            "embedding_similarity": 0.75
        }
    },
    PatternType.DOCUMENTATION: {
        "policy": ExtractionPolicy.INCLUSIVE,
        "thresholds": {
            "min_occurrences": 1,
            "confidence": 0.6,
            "embedding_similarity": 0.7
        }
    },
    PatternType.ARCHITECTURE: {
        "policy": ExtractionPolicy.STRICT,
        "thresholds": {
            "min_occurrences": 1,
            "confidence": 0.9,
            "embedding_similarity": 0.9
        }
    },
    PatternType.COMPONENT_DEPENDENCY: {
        "policy": ExtractionPolicy.BALANCED,
        "thresholds": {
            "min_occurrences": 2,
            "confidence": 0.7,
            "embedding_similarity": 0.8
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

def get_default_thresholds() -> Dict[str, Any]:
    """Get a copy of the default threshold settings."""
    return DEFAULT_THRESHOLDS.copy()

def get_projection_config(projection_type: str, **kwargs) -> Dict[str, Any]:
    """Get configuration for a specific graph projection type.
    
    Args:
        projection_type: Type of projection ('code', 'pattern', or 'combined')
        **kwargs: Additional parameters for name template formatting
        
    Returns:
        Dict containing projection configuration
    """
    config = GRAPH_PROJECTIONS.get(projection_type)
    if not config:
        raise ValueError(f"Unknown projection type: {projection_type}")
    
    return {
        "name": config["name_template"].format(**kwargs),
        "node_query": config["node_query"],
        "relationship_query": config["relationship_query"]
    }

def get_algorithm_config(algorithm_type: str) -> Dict[str, Any]:
    """Get configuration for a graph algorithm."""
    return GRAPH_ALGORITHMS.get(algorithm_type, GRAPH_ALGORITHMS["similarity"])

def get_extraction_policy(pattern_type: PatternType) -> Dict[str, Any]:
    """Get extraction policy for a pattern type."""
    return EXTRACTION_POLICIES.get(pattern_type, 
                                 EXTRACTION_POLICIES[PatternType.CODE_STRUCTURE])

def get_language_rules(language: str) -> Dict[str, Any]:
    """Get rules for a specific programming language."""
    return LANGUAGE_RULES.get(language.lower(), LANGUAGE_RULES["default"])

def get_doc_pattern_rules(doc_type: str) -> Dict[str, Any]:
    """Get rules for a specific documentation type."""
    return DOC_PATTERN_RULES.get(doc_type.lower(), DOC_PATTERN_RULES["default"])

def get_pattern_extraction_config(pattern_type: PatternType) -> Dict[str, Any]:
    """Get extraction configuration for a pattern type."""
    return PATTERN_EXTRACTION.get(pattern_type, 
                                PATTERN_EXTRACTION[PatternType.CODE_STRUCTURE]) 