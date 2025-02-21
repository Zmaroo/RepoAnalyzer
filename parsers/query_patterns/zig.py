"""Query patterns for Zig files."""

from .common import COMMON_PATTERNS

ZIG_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (FnProto
                name: (IDENTIFIER) @syntax.function.name
                params: (ParamDeclList) @syntax.function.params
                return_type: (_)? @syntax.function.return_type) @syntax.function.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        },
        "struct": {
            "pattern": """
            (ContainerDecl
                name: (IDENTIFIER) @syntax.struct.name
                members: (_)* @syntax.struct.members) @syntax.struct.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.struct.name", {}).get("text", ""),
                "type": "struct"
            }
        },
        "enum": {
            "pattern": """
            (ErrorSetDecl
                fields: (IDENTIFIER)* @syntax.enum.fields) @syntax.enum.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            (VarDecl
                name: (IDENTIFIER) @semantics.variable.name
                type: (_)? @semantics.variable.type
                value: (_)? @semantics.variable.value) @semantics.variable.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.variable.name", {}).get("text", ""),
                "type": "variable"
            }
        },
        "type": {
            "pattern": """
            [
                (ErrorUnionExpr
                    exception: (_)? @semantics.type.error
                    type: (_) @semantics.type.value) @semantics.type.def,
                (PrefixTypeOp
                    operator: (_) @semantics.type.operator
                    type: (_) @semantics.type.value) @semantics.type.def
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (BinaryExpr) @semantics.expression.binary,
                (UnaryExpr) @semantics.expression.unary,
                (GroupedExpr) @semantics.expression.grouped,
                (InitList) @semantics.expression.init
            ]
            """
        }
    },

    "documentation": {
        "docstring": {
            "pattern": """
            (container_doc_comment) @documentation.docstring
            """
        },
        "comment": {
            "pattern": """
            [
                (doc_comment) @documentation.comment,
                (line_comment) @documentation.comment
            ]
            """
        }
    },

    "structure": {
        "namespace": {
            "pattern": """
            (Block
                statements: (_)* @structure.namespace.content) @structure.namespace.def
            """
        },
        "import": {
            "pattern": """
            (TopLevelDecl
                name: (IDENTIFIER) @structure.import.name
                value: (_) @structure.import.value) @structure.import.def
            """
        }
    }
} 