"""Query patterns for Solidity files.

This module provides Solidity-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "solidity"

@dataclass
class SolidityPatternContext(PatternContext):
    """Solidity-specific pattern context."""
    contract_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    modifier_names: Set[str] = field(default_factory=set)
    has_inheritance: bool = False
    has_modifiers: bool = False
    has_events: bool = False
    has_libraries: bool = False
    has_interfaces: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.contract_names)}:{self.has_inheritance}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "contract": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "event": PatternPerformanceMetrics(),
    "modifier": PatternPerformanceMetrics(),
    "storage": PatternPerformanceMetrics()
}

SOLIDITY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "contract": ResilientPattern(
                pattern="""
                [
                    (contract_definition
                        name: (identifier) @syntax.contract.name
                        base: (inheritance_specifier 
                            name: (identifier) @syntax.contract.base.name)* @syntax.contract.base
                        body: (contract_body) @syntax.contract.body) @syntax.contract.def,
                    (interface_definition
                        name: (identifier) @syntax.interface.name
                        body: (contract_body) @syntax.interface.body) @syntax.interface.def,
                    (library_definition
                        name: (identifier) @syntax.library.name
                        body: (contract_body) @syntax.library.body) @syntax.library.def
                ]
                """,
                extract=lambda node: {
                    "type": "contract",
                    "name": (
                        node["captures"].get("syntax.contract.name", {}).get("text", "") or
                        node["captures"].get("syntax.interface.name", {}).get("text", "") or
                        node["captures"].get("syntax.library.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.contract.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.interface.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.library.def", {}).get("start_point", [0])[0]
                    ),
                    "is_interface": "syntax.interface.def" in node["captures"],
                    "is_library": "syntax.library.def" in node["captures"],
                    "has_inheritance": "syntax.contract.base" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "event", "modifier"],
                        PatternRelationType.DEPENDS_ON: ["contract"]
                    }
                },
                name="contract",
                description="Matches Solidity contract declarations",
                examples=["contract MyContract is BaseContract", "interface IToken", "library SafeMath"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["contract"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.func.name
                        visibility: [(public) (private) (internal) (external)] @syntax.func.visibility
                        state_mutability: [(pure) (view) (payable)] @syntax.func.mutability
                        parameters: (parameter_list) @syntax.func.params
                        return_parameters: (parameter_list)? @syntax.func.returns
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (modifier_definition
                        name: (identifier) @syntax.modifier.name
                        parameters: (parameter_list)? @syntax.modifier.params
                        body: (block) @syntax.modifier.body) @syntax.modifier.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.modifier.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.modifier.def", {}).get("start_point", [0])[0]
                    ),
                    "is_modifier": "syntax.modifier.def" in node["captures"],
                    "visibility": node["captures"].get("syntax.func.visibility", {}).get("text", ""),
                    "mutability": node["captures"].get("syntax.func.mutability", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "statement"],
                        PatternRelationType.DEPENDS_ON: ["contract", "modifier"]
                    }
                },
                name="function",
                description="Matches Solidity function declarations",
                examples=["function transfer(address to, uint256 amount) public", "modifier onlyOwner"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.STORAGE: {
            "storage": AdaptivePattern(
                pattern="""
                [
                    (state_variable_declaration
                        type: (type_name) @storage.var.type
                        visibility: [(public) (private) (internal)] @storage.var.visibility
                        name: (identifier) @storage.var.name
                        value: (_)? @storage.var.value) @storage.var.def,
                    (struct_declaration
                        name: (identifier) @storage.struct.name
                        members: (struct_member
                            type: (type_name) @storage.struct.member.type
                            name: (identifier) @storage.struct.member.name)* @storage.struct.members) @storage.struct.def,
                    (enum_declaration
                        name: (identifier) @storage.enum.name
                        members: (enum_value
                            name: (identifier) @storage.enum.value.name
                            value: (_)? @storage.enum.value.value)* @storage.enum.values) @storage.enum.def,
                    (mapping
                        key: (mapping_key) @storage.mapping.key
                        value: (type_name) @storage.mapping.value) @storage.mapping.def
                ]
                """,
                extract=lambda node: {
                    "type": "storage",
                    "line_number": (
                        node["captures"].get("storage.var.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.struct.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.enum.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.mapping.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("storage.var.name", {}).get("text", "") or
                        node["captures"].get("storage.struct.name", {}).get("text", "") or
                        node["captures"].get("storage.enum.name", {}).get("text", "")
                    ),
                    "storage_type": (
                        "state_variable" if "storage.var.def" in node["captures"] else
                        "struct" if "storage.struct.def" in node["captures"] else
                        "enum" if "storage.enum.def" in node["captures"] else
                        "mapping" if "storage.mapping.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["contract"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="storage",
                description="Matches Solidity storage declarations",
                examples=["uint256 public balance;", "struct User { address addr; }", "enum Status { Active, Inactive }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.STORAGE,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["storage"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_solidity_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Solidity content for repository learning."""
    patterns = []
    context = SolidityPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SOLIDITY_PATTERNS:
                category_patterns = SOLIDITY_PATTERNS[category]
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
                                    if match["type"] == "contract":
                                        context.contract_names.add(match["name"])
                                        if match["is_interface"]:
                                            context.has_interfaces = True
                                        elif match["is_library"]:
                                            context.has_libraries = True
                                        elif match["has_inheritance"]:
                                            context.has_inheritance = True
                                    elif match["type"] == "function":
                                        if match["is_modifier"]:
                                            context.has_modifiers = True
                                            context.modifier_names.add(match["name"])
                                        else:
                                            context.function_names.add(match["name"])
                                    elif match["type"] == "storage":
                                        if match["storage_type"] == "enum":
                                            context.has_events = True
                                            context.event_names.add(match["name"])
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Solidity patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "contract": {
        PatternRelationType.CONTAINS: ["function", "event", "modifier"],
        PatternRelationType.DEPENDS_ON: ["contract"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "statement"],
        PatternRelationType.DEPENDS_ON: ["contract", "modifier"]
    },
    "storage": {
        PatternRelationType.CONTAINED_BY: ["contract"],
        PatternRelationType.DEPENDS_ON: ["type"]
    }
}

# Export public interfaces
__all__ = [
    'SOLIDITY_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_solidity_patterns_for_learning',
    'SolidityPatternContext',
    'pattern_learner'
] 