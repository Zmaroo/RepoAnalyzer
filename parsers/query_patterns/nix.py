"""
Query patterns for Nix files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

NIX_PATTERNS_FOR_LEARNING = {
    "functional_patterns": {
        "pattern": """
        [
            (function_expression
                params: (formals) @func.params
                body: (_) @func.body) @func.def,
            (lambda
                params: (formals) @func.lambda.params
                body: (_) @func.lambda.body) @func.lambda
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional",
            "is_function": "func.def" in node["captures"],
            "is_lambda": "func.lambda" in node["captures"],
            "param_count": len((node["captures"].get("func.params", {}).get("text", "") or 
                             node["captures"].get("func.lambda.params", {}).get("text", "") or "").split(",")),
            "uses_pattern_matching": "{" in (node["captures"].get("func.params", {}).get("text", "") or 
                                        node["captures"].get("func.lambda.params", {}).get("text", "") or "")
        }
    },
    
    "attrset_patterns": {
        "pattern": """
        [
            (attrset_expression
                bindings: (binding_set) @attr.set.bindings) @attr.set,
            (rec_attrset_expression
                bindings: (binding_set) @attr.rec.bindings) @attr.rec,
            (binding
                attrpath: (attrpath) @attr.binding.path
                expression: (_) @attr.binding.value) @attr.binding
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "attribute_set",
            "is_regular_attrset": "attr.set" in node["captures"],
            "is_recursive_attrset": "attr.rec" in node["captures"],
            "is_binding": "attr.binding" in node["captures"],
            "attribute_path": node["captures"].get("attr.binding.path", {}).get("text", ""),
            "binding_count": len((node["captures"].get("attr.set.bindings", {}).get("text", "") or 
                               node["captures"].get("attr.rec.bindings", {}).get("text", "") or "").split(";")),
            "uses_nested_attrs": "." in (node["captures"].get("attr.binding.path", {}).get("text", "") or "")
        }
    },
    
    "derivation_patterns": {
        "pattern": """
        [
            (call_expression
                function: [(identifier) (select_expression)]
                arguments: (attrset_expression)* @deriv.args
                (#match? @deriv.args "stdenv\\.mkDerivation|buildPythonPackage|buildRustPackage|buildGoModule")) @deriv.call,
            (binding
                attrpath: (attrpath) @deriv.attr.name
                (#match? @deriv.attr.name "^(name|version|src|buildInputs|propagatedBuildInputs|nativeBuildInputs)$")
                expression: (_) @deriv.attr.value) @deriv.attr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "derivation",
            "is_derivation_call": "deriv.call" in node["captures"],
            "is_derivation_attribute": "deriv.attr" in node["captures"],
            "attribute_name": node["captures"].get("deriv.attr.name", {}).get("text", ""),
            "uses_fetch_from_github": "fetchFromGitHub" in (node["captures"].get("deriv.attr.value", {}).get("text", "") or ""),
            "uses_standard_environment": "stdenv" in (node["captures"].get("deriv.args", {}).get("text", "") or "")
        }
    },
    
    "import_patterns": {
        "pattern": """
        [
            (import_expression
                path: (_) @import.path) @import.expr,
            (with_expression
                environment: (_) @with.env
                body: (_) @with.body) @with.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "import",
            "is_import": "import.expr" in node["captures"],
            "is_with": "with.expr" in node["captures"],
            "import_path": node["captures"].get("import.path", {}).get("text", ""),
            "imports_nixpkgs": "nixpkgs" in (node["captures"].get("import.path", {}).get("text", "") or ""),
            "uses_with_statement": "with.expr" in node["captures"],
            "with_environment": node["captures"].get("with.env", {}).get("text", "")
        }
    }
}

NIX_PATTERNS = {
    **COMMON_PATTERNS,
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function
                        formals: (formals
                            (_)* @syntax.function.params)
                        body: (_) @syntax.function.body) @syntax.function.def,
                    (let_in
                        bindings: (binding_set
                            (_)* @syntax.function.let.bindings)
                        body: (_) @syntax.function.let.body) @syntax.function.let
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "is_let_binding": "syntax.function.let" in node["captures"],
                    "has_params": "syntax.function.params" in node["captures"],
                    "has_bindings": "syntax.function.let.bindings" in node["captures"]
                }
            ),
            "attribute": QueryPattern(
                pattern="""
                [
                    (attrset
                        bindings: (_)* @syntax.attr.bindings) @syntax.attr.set,
                    (rec_attrset
                        bindings: (_)* @syntax.attr.rec.bindings) @syntax.attr.rec.set,
                    (inherit
                        attrs: (_)* @syntax.attr.inherit.attrs) @syntax.attr.inherit
                ]
                """,
                extract=lambda node: {
                    "type": "attribute",
                    "is_recursive": "syntax.attr.rec.set" in node["captures"],
                    "is_inherit": "syntax.attr.inherit" in node["captures"],
                    "has_bindings": any(
                        key in node["captures"] for key in 
                        ["syntax.attr.bindings", "syntax.attr.rec.bindings"]
                    )
                }
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "binding": QueryPattern(
                pattern="""
                [
                    (binding
                        name: (_) @semantics.binding.name
                        value: (_) @semantics.binding.value) @semantics.binding.def,
                    (inherit_from
                        attrs: (_)* @semantics.binding.inherit.attrs
                        expr: (_) @semantics.binding.inherit.from) @semantics.binding.inherit
                ]
                """,
                extract=lambda node: {
                    "type": "binding",
                    "name": node["captures"].get("semantics.binding.name", {}).get("text", ""),
                    "is_inherit": "semantics.binding.inherit" in node["captures"],
                    "has_value": "semantics.binding.value" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment.line,
                    (comment_block) @documentation.comment.block
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment.line", {}).get("text", "") or
                        node["captures"].get("documentation.comment.block", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_block": "documentation.comment.block" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "derivation_patterns": QueryPattern(
                pattern="""
                [
                    (apply_expression
                        function: (_) @learning.deriv.func
                        argument: (_) @learning.deriv.args
                        (#match? @learning.deriv.func "mkDerivation|stdenv\\.mkDerivation")) @learning.deriv,
                    (binding
                        name: (_) @learning.deriv.attr.name
                        (#match-any? @learning.deriv.attr.name "^(src|version|buildInputs|nativeBuildInputs|propagatedBuildInputs)$")
                        value: (_) @learning.deriv.attr.value) @learning.deriv.attr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "derivation",
                    "uses_mkDerivation": "learning.deriv" in node["captures"],
                    "has_common_attr": "learning.deriv.attr" in node["captures"],
                    "derivation_type": node["captures"].get("learning.deriv.func", {}).get("text", ""),
                    "attribute_name": node["captures"].get("learning.deriv.attr.name", {}).get("text", "")
                }
            )
        },
        PatternPurpose.DEPENDENCIES: {
            "dependency_management": QueryPattern(
                pattern="""
                [
                    (binding
                        name: (_) @learning.dep.name
                        (#match-any? @learning.dep.name "^(dependencies|buildInputs|nativeBuildInputs|propagatedBuildInputs)$")
                        value: (_) @learning.dep.value) @learning.dep.def,
                    (with_expression
                        package: (_) @learning.dep.with.pkg
                        body: (_) @learning.dep.with.body) @learning.dep.with
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "dependency_management",
                    "is_dependency_list": "learning.dep.def" in node["captures"],
                    "uses_with": "learning.dep.with" in node["captures"],
                    "dependency_type": node["captures"].get("learning.dep.name", {}).get("text", ""),
                    "with_package": node["captures"].get("learning.dep.with.pkg", {}).get("text", "")
                }
            )
        },
        PatternPurpose.PACKAGING: {
            "package_configuration": QueryPattern(
                pattern="""
                [
                    (binding
                        name: (_) @learning.pkg.meta.name
                        (#match-any? @learning.pkg.meta.name "^(meta|homepage|description|license|maintainers)$")
                        value: (_) @learning.pkg.meta.value) @learning.pkg.meta.def,
                    (binding
                        name: (_) @learning.pkg.build.name
                        (#match-any? @learning.pkg.build.name "^(configurePhase|buildPhase|installPhase|fixupPhase)$")
                        value: (_) @learning.pkg.build.value) @learning.pkg.build.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "package_configuration",
                    "is_metadata": "learning.pkg.meta.def" in node["captures"],
                    "is_build_phase": "learning.pkg.build.def" in node["captures"],
                    "attribute_name": (
                        node["captures"].get("learning.pkg.meta.name", {}).get("text", "") or
                        node["captures"].get("learning.pkg.build.name", {}).get("text", "")
                    )
                }
            )
        }
    },
    
    "REPOSITORY_LEARNING": NIX_PATTERNS_FOR_LEARNING
} 