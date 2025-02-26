"""
Query patterns for Nix files.
"""

from parsers.types import FileType
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
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_expression
                    params: (formals) @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def,
                (lambda
                    params: (formals) @syntax.function.lambda.params
                    body: (_) @syntax.function.lambda.body) @syntax.function.lambda
            ]
            """
        },
        "conditional": {
            "pattern": """
            (if_expression
                condition: (_) @syntax.conditional.if.condition
                consequence: (_) @syntax.conditional.if.body
                alternative: (_)? @syntax.conditional.if.else) @syntax.conditional.if
            """
        },
        "let": {
            "pattern": """
            [
                (let_expression
                    body: (_) @syntax.let.body) @syntax.let.def,
                (let_attrset_expression
                    bindings: (binding_set) @syntax.let.attrs.bindings) @syntax.let.attrs
            ]
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (binding
                    attrpath: (attrpath) @semantics.variable.name
                    expression: (_) @semantics.variable.value) @semantics.variable.def,
                (inherit
                    attrs: (inherited_attrs) @semantics.variable.inherit.attrs) @semantics.variable.inherit,
                (inherit_from
                    expression: (_) @semantics.variable.inherit.from.expr
                    attrs: (inherited_attrs) @semantics.variable.inherit.from.attrs) @semantics.variable.inherit.from
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (binary_expression
                    left: (_) @semantics.expression.binary.left
                    operator: _ @semantics.expression.binary.op
                    right: (_) @semantics.expression.binary.right) @semantics.expression.binary,
                (unary_expression
                    operator: _ @semantics.expression.unary.op
                    argument: (_) @semantics.expression.unary.arg) @semantics.expression.unary
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            [
                (attrset_expression
                    bindings: (binding_set) @structure.namespace.attrs) @structure.namespace.def,
                (rec_attrset_expression
                    bindings: (binding_set) @structure.namespace.rec.attrs) @structure.namespace.rec
            ]
            """
        },
        "import": {
            "pattern": """
            [
                (import_expression
                    path: (_) @structure.import.path) @structure.import.def,
                (with_expression
                    environment: (_) @structure.with.env
                    body: (_) @structure.with.body) @structure.with
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },
    
    "REPOSITORY_LEARNING": NIX_PATTERNS_FOR_LEARNING
} 