"""Tree-sitter patterns for Ada programming language."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

ADA_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (subprogram_body
                        (procedure_specification
                            name: (identifier) @syntax.function.name
                            parameters: (parameter_specification
                                [(identifier) @syntax.function.param.name
                                 (mode_in) @syntax.function.param.mode.in
                                 (mode_out) @syntax.function.param.mode.out
                                 (mode_in_out) @syntax.function.param.mode.inout]*) @syntax.function.params) @syntax.function.procedure
                        body: (handled_sequence_of_statements) @syntax.function.body) @syntax.function.def,
                    
                    (subprogram_body
                        (function_specification
                            name: (identifier) @syntax.function.name
                            parameters: (parameter_specification)? @syntax.function.params
                            return_type: (_) @syntax.function.return_type) @syntax.function.spec
                        body: (handled_sequence_of_statements) @syntax.function.body) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "procedure" if "syntax.function.procedure" in node["captures"] else "function"
                }
            ),
            "package": QueryPattern(
                pattern="""
                [
                    (package_declaration
                        name: (identifier) @syntax.package.name
                        body: (package_specification
                            [(use_clause) @syntax.package.use
                             (with_clause) @syntax.package.with]*) @syntax.package.spec) @syntax.package.def,
                    
                    (package_body
                        name: (identifier) @syntax.package.body.name
                        body: (handled_sequence_of_statements) @syntax.package.body.statements) @syntax.package.body
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.package.name", {}).get("text", "") or
                           node["captures"].get("syntax.package.body.name", {}).get("text", "")
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "type": QueryPattern(
                pattern="""
                [
                    (full_type_declaration
                        name: (identifier) @semantics.type.name
                        definition: [(derived_type_definition) @semantics.type.derived
                                   (record_type_definition) @semantics.type.record
                                   (array_type_definition) @semantics.type.array
                                   (enumeration_type_definition) @semantics.type.enum]) @semantics.type.def,
                    
                    (subtype_declaration
                        name: (identifier) @semantics.subtype.name
                        definition: (_) @semantics.subtype.def) @semantics.subtype
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", "") or
                           node["captures"].get("semantics.subtype.name", {}).get("text", ""),
                    "kind": ("subtype" if "semantics.subtype" in node["captures"] else
                            "derived" if "semantics.type.derived" in node["captures"] else
                            "record" if "semantics.type.record" in node["captures"] else
                            "array" if "semantics.type.array" in node["captures"] else
                            "enum" if "semantics.type.enum" in node["captures"] else
                            "type")
                }
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                [
                    (with_clause
                        [(identifier) (selected_component)]+ @structure.with.name
                        is_limited: (limited)? @structure.with.limited
                        is_private: (private)? @structure.with.private) @structure.with,
                    
                    (use_clause
                        [(identifier) (selected_component)]+ @structure.use.name) @structure.use
                ]
                """,
                extract=lambda node: {
                    "withs": [w.get("text", "") for w in node["captures"].get("structure.with.name", [])],
                    "uses": [u.get("text", "") for u in node["captures"].get("structure.use.name", [])]
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (pragma_g) @documentation.pragma
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "pragma" if "documentation.pragma" in node["captures"] else "comment"
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "naming_conventions": QueryPattern(
                pattern="""
                [
                    (identifier) @naming.identifier
                    (#match? @naming.identifier "^[A-Z][a-z0-9_]*$")
                ]
                """,
                extract=lambda node: {
                    "type": "naming_convention_pattern",
                    "name": node["node"].text.decode('utf8'),
                    "convention": "mixed_case",
                    "follows_convention": True
                }
            ),
            "error_handling": QueryPattern(
                pattern="""
                [
                    (exception_handler
                        (exception_choice) @error.exception
                        (handled_sequence_of_statements) @error.handler) @error.handler.def
                ]
                """,
                extract=lambda node: {
                    "type": "error_handling_pattern",
                    "exception": node["captures"].get("error.exception", {}).get("text", ""),
                    "has_handler": True
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "code_structure": QueryPattern(
                pattern="""
                [
                    (package_declaration
                        name: (identifier) @structure.package.name
                        body: (package_specification) @structure.package.spec) @structure.package,
                        
                    (subprogram_body
                        [(procedure_specification) (function_specification)] @structure.subprogram.spec
                        body: (handled_sequence_of_statements) @structure.subprogram.body) @structure.subprogram
                ]
                """,
                extract=lambda node: {
                    "type": "code_structure_pattern",
                    "structure_type": "package" if "structure.package" in node["captures"] else "subprogram",
                    "name": node["captures"].get("structure.package.name", {}).get("text", "")
                }
            )
        }
    }
} 