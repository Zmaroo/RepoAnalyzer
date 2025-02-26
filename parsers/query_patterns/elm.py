"""Elm-specific Tree-sitter patterns.

This module defines basic queries for capturing Elm constructs such as module declarations,
value declarations, type aliases, and union types.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

ELM_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (module_declaration
                name: (upper_case_qid) @naming.module.name) @naming.module,
                
            (type_declaration
                name: (upper_case_identifier) @naming.type.name) @naming.type,
                
            (type_alias_declaration
                name: (upper_case_identifier) @naming.alias.name) @naming.alias,
                
            (value_declaration
                pattern: (lower_pattern) @naming.function.name) @naming.function,
                
            (lower_pattern) @naming.variable
        ]
        """,
        "extract": lambda node: {
            "entity_type": ("module" if "naming.module.name" in node["captures"] else
                         "type" if "naming.type.name" in node["captures"] else
                         "alias" if "naming.alias.name" in node["captures"] else
                         "function" if "naming.function.name" in node["captures"] else
                         "variable"),
            "name": (node["captures"].get("naming.module.name", {}).get("text", "") or
                   node["captures"].get("naming.type.name", {}).get("text", "") or
                   node["captures"].get("naming.alias.name", {}).get("text", "") or
                   node["captures"].get("naming.function.name", {}).get("text", "") or
                   node["captures"].get("naming.variable", {}).get("text", "")),
            "uses_camel_case": any(
                name and name[0].islower() and any(c.isupper() for c in name)
                for name in [node["captures"].get("naming.function.name", {}).get("text", ""),
                           node["captures"].get("naming.variable", {}).get("text", "")]
                if name
            ),
            "uses_pascal_case": any(
                name and name[0].isupper() and not "_" in name
                for name in [node["captures"].get("naming.module.name", {}).get("text", ""),
                           node["captures"].get("naming.type.name", {}).get("text", ""),
                           node["captures"].get("naming.alias.name", {}).get("text", "")]
                if name
            )
        }
    },
    
    "type_system": {
        "pattern": """
        [
            (type_annotation
                name: (_) @type_system.annotation.name
                expression: (_) @type_system.annotation.expr) @type_system.annotation,
                
            (type_declaration
                name: (upper_case_identifier) @type_system.union.name
                type_variables: (lower_pattern)* @type_system.union.type_vars
                constructors: (union_variant)+ @type_system.union.constructors) @type_system.union,
                
            (type_alias_declaration
                name: (upper_case_identifier) @type_system.alias.name
                type_variables: (lower_pattern)* @type_system.alias.type_vars
                type_expression: (_) @type_system.alias.type) @type_system.alias,
                
            (type_expression
                (_) @type_system.type_expr) @type_system.type
        ]
        """,
        "extract": lambda node: {
            "pattern_type": ("annotation" if "type_system.annotation" in node["captures"] else
                          "union" if "type_system.union" in node["captures"] else
                          "alias" if "type_system.alias" in node["captures"] else
                          "type_expression"),
            "uses_type_annotation": "type_system.annotation" in node["captures"],
            "uses_union_types": "type_system.union" in node["captures"],
            "uses_type_aliases": "type_system.alias" in node["captures"],
            "has_type_variables": any(
                type_vars and type_vars.strip() 
                for type_vars in [
                    node["captures"].get("type_system.union.type_vars", {}).get("text", ""),
                    node["captures"].get("type_system.alias.type_vars", {}).get("text", "")
                ]
            )
        }
    },
    
    "functional_patterns": {
        "pattern": """
        [
            (case_of_expr
                expr: (_) @fp.case.expr
                branches: (case_of_branch)+ @fp.case.branches) @fp.case,
                
            (let_in_expr
                declarations: (value_declaration)+ @fp.let.decls
                expression: (_) @fp.let.expr) @fp.let,
                
            (function_call_expr
                target: (_) @fp.call.func
                arguments: (_)+ @fp.call.args) @fp.call,
                
            (lambda_expr
                patterns: (pattern)+ @fp.lambda.params
                expr: (_) @fp.lambda.body) @fp.lambda,
                
            (pipe_right_expr
                left: (_) @fp.pipe.left
                right: (_) @fp.pipe.right) @fp.pipe
        ]
        """,
        "extract": lambda node: {
            "uses_pattern_matching": "fp.case" in node["captures"],
            "uses_let_expressions": "fp.let" in node["captures"],
            "uses_lambda": "fp.lambda" in node["captures"],
            "uses_pipe": "fp.pipe" in node["captures"],
            "pattern_type": ("case" if "fp.case" in node["captures"] else
                          "let" if "fp.let" in node["captures"] else
                          "lambda" if "fp.lambda" in node["captures"] else
                          "pipe" if "fp.pipe" in node["captures"] else
                          "function_call")
        }
    },
    
    "module_organization": {
        "pattern": """
        [
            (module_declaration
                name: (upper_case_qid) @mod.name
                exposing: (exposed_values) @mod.exposing) @mod.decl,
                
            (import_declaration
                module_name: (upper_case_qid) @mod.import.name
                as_name: (upper_case_identifier)? @mod.import.alias
                exposing: (exposed_values)? @mod.import.exposing) @mod.import,
                
            (port_annotation
                name: (_) @mod.port.name) @mod.port
        ]
        """,
        "extract": lambda node: {
            "module_name": node["captures"].get("mod.name", {}).get("text", ""),
            "imports_with_alias": "mod.import.alias" in node["captures"] and node["captures"].get("mod.import.alias", {}).get("text", ""),
            "exposes_all": "exposing (..)" in node["captures"].get("mod.exposing", {}).get("text", ""),
            "uses_ports": "mod.port" in node["captures"],
            "module_type": "port" if "mod.port" in node["captures"] else "regular"
        }
    }
}

ELM_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            (value_declaration
              pattern: (lower_pattern) @syntax.function.name
              type_annotation: (type_annotation)? @syntax.function.type
              value: (value_expr) @syntax.function.body) @syntax.function.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "type": "function"
            }
        },
        "class": {
            "pattern": """
            [
                (type_declaration
                    name: (upper_case_identifier) @syntax.class.name
                    type_variables: (lower_pattern)* @syntax.class.type_vars
                    constructors: (union_variant)+ @syntax.class.constructors) @syntax.class.def,
                (type_alias_declaration
                    name: (upper_case_identifier) @syntax.class.name
                    type_variables: (lower_pattern)* @syntax.class.type_vars
                    type_expression: (_) @syntax.class.type) @syntax.class.def
            ]
            """
        }
    },

    "semantics": {
        "type": {
            "pattern": """
            [
                (type_annotation
                    name: (_) @semantics.type.name
                    expression: (_) @semantics.type.expr) @semantics.type.def,
                (type_variable
                    name: (lower_case_identifier) @semantics.type.var) @semantics.type.def
            ]
            """
        },
        "variable": {
            "pattern": """
            [
                (lower_pattern) @semantics.variable,
                (record_pattern
                    fields: (lower_pattern)+ @semantics.variable.fields) @semantics.variable.def
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block
            ]
            """
        },
        "docstring": {
            "pattern": """
            (block_comment
                content: (_) @documentation.docstring.content
                (#match? @documentation.docstring.content "^\\|\\s*@docs")) @documentation.docstring.def
            """
        }
    },

    "structure": {
        "module": {
            "pattern": """
            (module_declaration
                name: (upper_case_qid) @structure.module.name
                exposing: (exposed_values)? @structure.module.exports) @structure.module.def
            """
        },
        "import": {
            "pattern": """
            (import_declaration
                module_name: (upper_case_qid) @structure.import.module
                as_name: (upper_case_identifier)? @structure.import.alias
                exposing: (exposed_values)? @structure.import.exposed) @structure.import.def
            """
        }
    },
    
    "REPOSITORY_LEARNING": ELM_PATTERNS_FOR_LEARNING
}

# Additional metadata for pattern categories
PATTERN_METADATA = {
    "syntax": {
        "function": {
            "contains": ["type", "body"],
            "contained_by": ["namespace"]
        },
        "class": {
            "contains": ["type_vars", "constructors", "type"],
            "contained_by": ["namespace"]
        }
    },
    "structure": {
        "namespace": {
            "contains": ["exports", "function", "class", "variable"],
            "contained_by": []
        },
        "import": {
            "contains": ["exposed"],
            "contained_by": ["namespace"]
        }
    },
    "semantics": {
        "variable": {
            "contains": ["fields"],
            "contained_by": ["function", "expression"]
        },
        "expression": {
            "contains": ["args", "condition", "then", "else", "branches", "declarations"],
            "contained_by": ["function", "let_in_expr"]
        }
    },
    "documentation": {
        "docstring": {
            "contains": [],
            "contained_by": ["function", "class", "namespace"]
        },
        "comment": {
            "contains": [],
            "contained_by": ["function", "class", "namespace", "expression"]
        }
    }
} 