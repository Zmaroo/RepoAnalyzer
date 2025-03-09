"""
Query patterns for requirements.txt files.

This module provides requirements.txt-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.logger import log

# Language identifier
LANGUAGE = "requirements"

@dataclass
class RequirementsPatternContext(PatternContext):
    """Requirements.txt-specific pattern context."""
    package_names: Set[str] = field(default_factory=set)
    version_specs: Set[str] = field(default_factory=set)
    constraint_names: Set[str] = field(default_factory=set)
    has_versions: bool = False
    has_constraints: bool = False
    has_direct_urls: bool = False
    has_local_paths: bool = False
    has_editable: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.package_names)}:{self.has_versions}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "package": PatternPerformanceMetrics(),
    "version": PatternPerformanceMetrics(),
    "constraint": PatternPerformanceMetrics(),
    "url": PatternPerformanceMetrics(),
    "option": PatternPerformanceMetrics()
}

REQUIREMENTS_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "package": ResilientPattern(
                pattern="""
                [
                    (requirement
                        package: (package) @syntax.pkg.name
                        version_spec: (version_spec
                            version_cmp: (version_cmp) @syntax.pkg.cmp
                            version: (version) @syntax.pkg.version)? @syntax.pkg.version_spec
                        extras: (extras
                            package: (package)* @syntax.pkg.extras.package)? @syntax.pkg.extras) @syntax.pkg,
                    (requirement
                        package: (package) @syntax.direct.pkg
                        url_spec: (url_spec) @syntax.direct.url) @syntax.direct,
                    (requirement
                        package: (package) @syntax.local.pkg
                        path_spec: (path_spec) @syntax.local.path) @syntax.local
                ]
                """,
                extract=lambda node: {
                    "type": "package",
                    "name": (
                        node["captures"].get("syntax.pkg.name", {}).get("text", "") or
                        node["captures"].get("syntax.direct.pkg", {}).get("text", "") or
                        node["captures"].get("syntax.local.pkg", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.pkg", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.direct", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.local", {}).get("start_point", [0])[0]
                    ),
                    "has_version": "syntax.pkg.version_spec" in node["captures"],
                    "is_direct_url": "syntax.direct" in node["captures"],
                    "is_local_path": "syntax.local" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["version", "constraint"],
                        PatternRelationType.REFERENCED_BY: ["option"]
                    }
                },
                name="package",
                description="Matches requirements.txt package declarations",
                examples=["package==1.0.0", "package @ http://example.com", "./local/package"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["package"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            ),
            "constraint": ResilientPattern(
                pattern="""
                [
                    (requirement
                        marker_spec: (marker_spec
                            marker_var: (marker_var) @syntax.marker.var
                            marker_op: (marker_op) @syntax.marker.op
                            marker_value: [(quoted_string) (marker_var)] @syntax.marker.value) @syntax.marker.spec) @syntax.marker,
                    (requirement
                        version_spec: (version_spec
                            version_cmp: [(version_cmp) (version_cmp_multi)] @syntax.version.op
                            version: (version) @syntax.version.value) @syntax.version) @syntax.version.req
                ]
                """,
                extract=lambda node: {
                    "type": "constraint",
                    "line_number": (
                        node["captures"].get("syntax.marker", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.version.req", {}).get("start_point", [0])[0]
                    ),
                    "operator": (
                        node["captures"].get("syntax.marker.op", {}).get("text", "") or
                        node["captures"].get("syntax.version.op", {}).get("text", "")
                    ),
                    "is_marker": "syntax.marker" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["package"],
                        PatternRelationType.DEPENDS_ON: ["version"]
                    }
                },
                name="constraint",
                description="Matches requirements.txt constraints",
                examples=["package>=1.0.0", "package; python_version>='3.7'"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["constraint"],
                    "validation": {
                        "required_fields": ["operator"],
                        "name_format": None
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.OPTIONS: {
            "option": AdaptivePattern(
                pattern="""
                [
                    (global_opt
                        option: (option) @option.global.name
                        value: [(argument) (quoted_string) (path) (url)]* @option.global.value) @option.global,
                    (requirement_opt
                        option: (option) @option.req.name
                        value: [(argument) (quoted_string)] @option.req.value) @option.req
                ]
                """,
                extract=lambda node: {
                    "type": "option",
                    "line_number": (
                        node["captures"].get("option.global", {}).get("start_point", [0])[0] or
                        node["captures"].get("option.req", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("option.global.name", {}).get("text", "") or
                        node["captures"].get("option.req.name", {}).get("text", "")
                    ),
                    "is_global": "option.global" in node["captures"],
                    "relationships": {
                        PatternRelationType.APPLIES_TO: ["package"],
                        PatternRelationType.DEPENDS_ON: ["option"]
                    }
                },
                name="option",
                description="Matches requirements.txt options",
                examples=["-i https://pypi.org/simple", "--no-binary :all:"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.OPTIONS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["option"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^-{1,2}[a-z][a-z0-9-]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_requirements_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from requirements.txt content for repository learning."""
    patterns = []
    context = RequirementsPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in REQUIREMENTS_PATTERNS:
                category_patterns = REQUIREMENTS_PATTERNS[category]
                for purpose in category_patterns:
                    for pattern_name, pattern in category_patterns[purpose].items():
                        if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "purpose": purpose.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "package":
                                        context.package_names.add(match["name"])
                                        if match["has_version"]:
                                            context.has_versions = True
                                        if match["is_direct_url"]:
                                            context.has_direct_urls = True
                                        if match["is_local_path"]:
                                            context.has_local_paths = True
                                    elif match["type"] == "constraint":
                                        context.has_constraints = True
                                        if match["is_marker"]:
                                            context.constraint_names.add(match["operator"])
                                    elif match["type"] == "option":
                                        if match["name"] == "-e" or match["name"] == "--editable":
                                            context.has_editable = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting requirements.txt patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "package": {
        PatternRelationType.DEPENDS_ON: ["version", "constraint"],
        PatternRelationType.REFERENCED_BY: ["option"]
    },
    "constraint": {
        PatternRelationType.CONTAINED_BY: ["package"],
        PatternRelationType.DEPENDS_ON: ["version"]
    },
    "option": {
        PatternRelationType.APPLIES_TO: ["package"],
        PatternRelationType.DEPENDS_ON: ["option"]
    }
}

# Export public interfaces
__all__ = [
    'REQUIREMENTS_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_requirements_patterns_for_learning',
    'RequirementsPatternContext',
    'pattern_learner'
]