"""Query patterns for HCL files.

This module provides HCL-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "hcl"

@dataclass
class HCLPatternContext(PatternContext):
    """HCL-specific pattern context."""
    block_types: Set[str] = field(default_factory=set)
    resource_types: Set[str] = field(default_factory=set)
    provider_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    has_providers: bool = False
    has_variables: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.block_types)}:{len(self.resource_types)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "block": PatternPerformanceMetrics(),
    "resource": PatternPerformanceMetrics(),
    "provider": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "output": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics()
}

HCL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "block": ResilientPattern(
                pattern="""
                (block
                    type: (identifier) @syntax.block.type
                    labels: (string_lit)* @syntax.block.labels
                    body: (body) @syntax.block.body) @syntax.block.def
                """,
                extract=lambda node: {
                    "type": "block",
                    "block_type": node["captures"].get("syntax.block.type", {}).get("text", ""),
                    "labels": node["captures"].get("syntax.block.labels", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.block.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["attribute", "block"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="block",
                description="Matches HCL blocks",
                examples=["resource \"aws_instance\" \"web\" {"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["block"],
                    "validation": {
                        "required_fields": ["block_type", "labels"],
                        "block_type_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            ),
            "attribute": ResilientPattern(
                pattern="""
                (attribute
                    name: (identifier) @syntax.attr.name
                    value: (expression) @syntax.attr.value) @syntax.attr.def
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "name": node["captures"].get("syntax.attr.name", {}).get("text", ""),
                    "value": node["captures"].get("syntax.attr.value", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.attr.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["block"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="attribute",
                description="Matches HCL attributes",
                examples=["instance_type = \"t2.micro\""],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["attribute"],
                    "validation": {
                        "required_fields": ["name", "value"],
                        "name_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": AdaptivePattern(
                pattern="""
                (block
                    type: (identifier) @var.type
                    (#eq? @var.type "variable")
                    labels: (string_lit) @var.name
                    body: (body) @var.body) @var.def
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": node["captures"].get("var.name", {}).get("text", ""),
                    "body": node["captures"].get("var.body", {}).get("text", ""),
                    "line_number": node["captures"].get("var.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["attribute"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="variable",
                description="Matches variable definitions",
                examples=['variable "instance_type" {'],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["variable"],
                    "validation": {
                        "required_fields": ["name", "body"],
                        "name_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            ),
            "output": AdaptivePattern(
                pattern="""
                (block
                    type: (identifier) @output.type
                    (#eq? @output.type "output")
                    labels: (string_lit) @output.name
                    body: (body) @output.body) @output.def
                """,
                extract=lambda node: {
                    "type": "output",
                    "name": node["captures"].get("output.name", {}).get("text", ""),
                    "body": node["captures"].get("output.body", {}).get("text", ""),
                    "line_number": node["captures"].get("output.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.REFERENCES: ["variable", "resource"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="output",
                description="Matches output definitions",
                examples=['output "instance_ip" {'],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["output"],
                    "validation": {
                        "required_fields": ["name", "body"],
                        "name_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.INFRASTRUCTURE: {
            "resource_patterns": AdaptivePattern(
                pattern="""
                [
                    (block
                        type: (identifier) @res.block.type
                        (#match? @res.block.type "^resource$")
                        labels: [
                            (string_lit) @res.block.resource_type
                            (string_lit) @res.block.resource_name
                        ]
                        body: (body) @res.block.body) @res.block,
                        
                    (block
                        type: (identifier) @res.data.type
                        (#match? @res.data.type "^data$")
                        labels: [
                            (string_lit) @res.data.data_type
                            (string_lit) @res.data.data_name
                        ]
                        body: (body) @res.data.body) @res.data
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "resource_definition" if "res.block" in node["captures"] else "data_source",
                    "resource_type": node["captures"].get("res.block.resource_type", {}).get("text", ""),
                    "resource_name": node["captures"].get("res.block.resource_name", {}).get("text", ""),
                    "data_type": node["captures"].get("res.data.data_type", {}).get("text", ""),
                    "data_name": node["captures"].get("res.data.data_name", {}).get("text", ""),
                    "is_resource": "res.block" in node["captures"],
                    "is_data_source": "res.data" in node["captures"],
                    "definition_body_size": len((node["captures"].get("res.block.body", {}).get("text", "") or 
                                            node["captures"].get("res.data.body", {}).get("text", "") or "").split("\n")),
                    "line_number": node["captures"].get("res.block", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["provider"],
                        PatternRelationType.REFERENCES: ["variable"]
                    }
                },
                name="resource_patterns",
                description="Matches resource and data source patterns",
                examples=['resource "aws_instance" "web" {'],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.INFRASTRUCTURE,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["resource"],
                    "validation": {
                        "required_fields": ["resource_type", "resource_name"],
                        "resource_type_format": r'^[a-z][a-z0-9_]*$',
                        "resource_name_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.PROVIDERS: {
            "provider_configuration": AdaptivePattern(
                pattern="""
                [
                    (block
                        type: (identifier) @prov.block.type
                        (#match? @prov.block.type "^provider$")
                        labels: (string_lit) @prov.block.name
                        body: (body) @prov.block.body) @prov.block,
                        
                    (block
                        type: (identifier) @prov.required.type
                        (#match? @prov.required.type "^required_providers$")
                        body: (body) @prov.required.body) @prov.required
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "provider_block" if "prov.block" in node["captures"] else
                        "required_providers" if "prov.required" in node["captures"] else
                        "other"
                    ),
                    "provider_name": node["captures"].get("prov.block.name", {}).get("text", "").strip('"\''),
                    "provider_configuration": node["captures"].get("prov.block.body", {}).get("text", ""),
                    "requires_multiple_providers": "prov.required" in node["captures"],
                    "uses_version_constraints": "version" in (
                        node["captures"].get("prov.block.body", {}).get("text", "") or
                        node["captures"].get("prov.required.body", {}).get("text", "") or ""
                    ),
                    "line_number": node["captures"].get("prov.block", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["resource"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="provider_configuration",
                description="Matches provider configurations",
                examples=['provider "aws" {'],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.PROVIDERS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["provider"],
                    "validation": {
                        "required_fields": ["provider_name"],
                        "provider_name_format": r'^[a-z][a-z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.MODULES: {
            "module_patterns": AdaptivePattern(
                pattern="""
                [
                    (block
                        type: (identifier) @mod.block.type
                        (#match? @mod.block.type "^module$")
                        labels: (string_lit) @mod.block.name
                        body: (body) @mod.block.body) @mod.block,
                        
                    (attribute
                        name: (identifier) @mod.output.name
                        (#match? @mod.output.name "^output$")
                        value: (expression) @mod.output.value) @mod.output
                ]
                """,
                extract=lambda node: {
                    "pattern_type": (
                        "module_definition" if "mod.block" in node["captures"] else
                        "module_output" if "mod.output" in node["captures"] else
                        "other"
                    ),
                    "module_name": node["captures"].get("mod.block.name", {}).get("text", "").strip('"\''),
                    "uses_source_attribute": "source" in (node["captures"].get("mod.block.body", {}).get("text", "") or ""),
                    "passes_variables": "var." in (node["captures"].get("mod.block.body", {}).get("text", "") or ""),
                    "module_complexity": len((node["captures"].get("mod.block.body", {}).get("text", "") or "").split("\n")),
                    "line_number": node["captures"].get("mod.block", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.REFERENCES: ["variable"],
                        PatternRelationType.DEPENDS_ON: ["provider"]
                    }
                },
                name="module_patterns",
                description="Matches module patterns",
                examples=['module "vpc" {'],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.MODULES,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["module"],
                    "validation": {
                        "required_fields": ["module_name"],
                        "module_name_format": r'^[a-z][a-z0-9_-]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_hcl_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from HCL content for repository learning."""
    patterns = []
    context = HCLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in HCL_PATTERNS:
                category_patterns = HCL_PATTERNS[category]
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
                                    if match["type"] == "block":
                                        context.block_types.add(match["block_type"])
                                    elif match["type"] == "resource":
                                        context.resource_types.add(match["resource_type"])
                                    elif match["type"] == "provider":
                                        context.provider_names.add(match["provider_name"])
                                        context.has_providers = True
                                    elif match["type"] == "variable":
                                        context.variable_names.add(match["name"])
                                        context.has_variables = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting HCL patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "block": {
        PatternRelationType.CONTAINS: ["attribute", "block"],
        PatternRelationType.DEPENDS_ON: ["provider"]
    },
    "resource": {
        PatternRelationType.DEPENDS_ON: ["provider", "variable"],
        PatternRelationType.REFERENCED_BY: ["output"]
    },
    "provider": {
        PatternRelationType.REFERENCED_BY: ["resource", "module"],
        PatternRelationType.DEPENDS_ON: ["required_providers"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["resource", "module", "output"],
        PatternRelationType.DEPENDS_ON: []
    },
    "module": {
        PatternRelationType.REFERENCES: ["variable"],
        PatternRelationType.DEPENDS_ON: ["provider"]
    }
}

# Export public interfaces
__all__ = [
    'HCL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_hcl_patterns_for_learning',
    'HCLPatternContext',
    'pattern_learner'
] 