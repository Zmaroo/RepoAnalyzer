"""Python-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

PYTHON_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (parameters
                        [(identifier) @syntax.function.param.name
                         (typed_parameter
                            name: (identifier) @syntax.function.param.name
                            type: (type) @syntax.function.param.type)
                         (default_parameter
                            name: (identifier) @syntax.function.param.name
                            value: (_) @syntax.function.param.default)
                         (list_splat_pattern
                            name: (identifier) @syntax.function.param.args)
                         (dictionary_splat_pattern
                            name: (identifier) @syntax.function.param.kwargs)]* @syntax.function.params)
                    return_type: (type)? @syntax.function.return_type
                    body: (block) @syntax.function.body) @syntax.function.def,
                
                (class_definition
                    body: (block
                        (function_definition
                            decorators: (decorator
                                name: [(identifier) (attribute)]
                                (#match? @name "^(classmethod|staticmethod|property)$"))? @syntax.function.method.decorator
                            name: (identifier) @syntax.function.method.name
                            parameters: (parameters) @syntax.function.method.params
                            body: (block) @syntax.function.method.body) @syntax.function.method))
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "params": [p.text.decode('utf8') for p in node["captures"].get("syntax.function.param.name", [])],
                "decorators": [d.text.decode('utf8') for d in node["captures"].get("syntax.function.decorator.name", [])]
            }
        },
        "class": {
            "pattern": """
            (class_definition
                decorators: (decorator)* @syntax.class.decorators
                name: (identifier) @syntax.class.name
                type_parameters: (type_parameter)? @syntax.class.type_params
                superclasses: (argument_list
                    [(identifier) @syntax.class.base
                     (keyword_argument
                        name: (identifier) @syntax.class.metaclass.name
                        value: (_) @syntax.class.metaclass.value)]*)? @syntax.class.bases
                body: (block) @syntax.class.body) @syntax.class.def
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                "bases": [b.text.decode('utf8') for b in node["captures"].get("syntax.class.base", [])]
            }
        }
    },
    
    "semantics": {
        "type": {
            "pattern": """
            [
                (type_parameter
                    name: (identifier) @semantics.type.param.name
                    bound: (type)? @semantics.type.param.bound) @semantics.type.param,
                
                (union_type
                    types: (type)+ @semantics.type.union.member) @semantics.type.union,
                
                (generic_type
                    name: (identifier) @semantics.type.generic.name
                    type_arguments: (type_parameter_list)? @semantics.type.generic.args) @semantics.type.generic
            ]
            """,
            "extract": lambda node: {
                "type": node["captures"].get("semantics.type.annotation", {}).get("text", ""),
                "kind": ("type_param" if "semantics.type.param" in node["captures"] else
                        "union" if "semantics.type.union" in node["captures"] else
                        "generic" if "semantics.type.generic" in node["captures"] else
                        "annotation")
            }
        }
    },
    
    "documentation": {
        "docstring": {
            "pattern": """
            [
                (module
                    (expression_statement
                        (string) @documentation.module.docstring)) @documentation.module,
                
                (function_definition
                    body: (block
                        (expression_statement
                            (string) @documentation.function.docstring))) @documentation.function,
                
                (class_definition
                    body: (block
                        (expression_statement
                            (string) @documentation.class.docstring))) @documentation.class,
                
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.module.docstring", {}).get("text", "") or
                       node["captures"].get("documentation.function.docstring", {}).get("text", "") or
                       node["captures"].get("documentation.class.docstring", {}).get("text", "") or
                       node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    name: (dotted_name) @structure.import.module) @structure.import,
                
                (import_from_statement
                    module_name: (dotted_name)? @structure.import.from.module
                    name: [(dotted_name) (wildcard_import)] @structure.import.from.name) @structure.import.from
            ]
            """,
            "extract": lambda node: {
                "module": node["captures"].get("structure.import.module", {}).get("text", "") or
                         node["captures"].get("structure.import.from.module", {}).get("text", ""),
                "name": node["captures"].get("structure.import.name", {}).get("text", "") or
                        node["captures"].get("structure.import.from.name", {}).get("text", "")
            }
        }
    }
} 