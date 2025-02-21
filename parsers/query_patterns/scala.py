"""
Query patterns for Scala files.
"""

from .common import COMMON_PATTERNS

SCALA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    modifiers: [(annotation) (modifier)]* @syntax.function.modifier
                    name: (identifier) @syntax.function.name
                    type_parameters: (type_parameters
                        (type_parameter
                            name: (identifier) @syntax.function.type_param.name
                            bounds: (upper_bound)? @syntax.function.type_param.bound)*)? @syntax.function.type_params
                    parameters: (parameters
                        [(parameter
                            name: (identifier) @syntax.function.param.name
                            type: (_) @syntax.function.param.type
                            default: (_)? @syntax.function.param.default)
                         (implicit_parameter
                            name: (identifier) @syntax.function.param.implicit.name
                            type: (_) @syntax.function.param.implicit.type)]*) @syntax.function.params
                    return_type: (_)? @syntax.function.return_type
                    body: (_) @syntax.function.body) @syntax.function.def,
                
                (method_definition
                    modifiers: [(annotation) (modifier)]* @syntax.method.modifier
                    name: (identifier) @syntax.method.name
                    type_parameters: (type_parameters)? @syntax.method.type_params
                    parameters: (parameters)? @syntax.method.params
                    return_type: (_)? @syntax.method.return_type
                    body: (_) @syntax.method.body) @syntax.method.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.method.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in 
                            node["captures"].get("syntax.function.modifier", []) +
                            node["captures"].get("syntax.method.modifier", [])]
            }
        },
        
        "class": {
            "pattern": """
            [
                (class_definition
                    modifiers: [(annotation) (modifier)]* @syntax.class.modifier
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameters
                        (type_parameter
                            name: (identifier) @syntax.class.type_param.name
                            bounds: [(upper_bound) (lower_bound)]? @syntax.class.type_param.bound)*)? @syntax.class.type_params
                    constructor_parameters: (parameters)? @syntax.class.constructor_params
                    extends_clause: (extends_clause)? @syntax.class.extends
                    body: (_)? @syntax.class.body) @syntax.class.def,
                
                (object_definition
                    modifiers: [(annotation) (modifier)]* @syntax.object.modifier
                    name: (identifier) @syntax.object.name
                    extends_clause: (extends_clause)? @syntax.object.extends
                    body: (_)? @syntax.object.body) @syntax.object.def,
                
                (trait_definition
                    modifiers: [(annotation) (modifier)]* @syntax.trait.modifier
                    name: (identifier) @syntax.trait.name
                    type_parameters: (type_parameters)? @syntax.trait.type_params
                    extends_clause: (extends_clause)? @syntax.trait.extends
                    body: (_)? @syntax.trait.body) @syntax.trait.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                       node["captures"].get("syntax.object.name", {}).get("text", "") or
                       node["captures"].get("syntax.trait.name", {}).get("text", ""),
                "kind": ("class" if "syntax.class.def" in node["captures"] else
                        "object" if "syntax.object.def" in node["captures"] else
                        "trait")
            }
        }
    },
    
    "semantics": {
        "variable": {
            "pattern": """
            [
                (val_definition
                    modifiers: [(annotation) (modifier)]* @semantics.val.modifier
                    pattern: (identifier) @semantics.val.name
                    type: (_)? @semantics.val.type
                    value: (_) @semantics.val.value) @semantics.val.def,
                
                (var_definition
                    modifiers: [(annotation) (modifier)]* @semantics.var.modifier
                    pattern: (identifier) @semantics.var.name
                    type: (_)? @semantics.var.type
                    value: (_) @semantics.var.value) @semantics.var.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.val.name", {}).get("text", "") or
                       node["captures"].get("semantics.var.name", {}).get("text", ""),
                "kind": "val" if "semantics.val.def" in node["captures"] else "var"
            }
        },
        
        "type": {
            "pattern": """
            [
                (type_definition
                    modifiers: [(annotation) (modifier)]* @semantics.type.modifier
                    name: (identifier) @semantics.type.name
                    type_parameters: (type_parameters)? @semantics.type.params
                    type: (_) @semantics.type.value) @semantics.type.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("semantics.type.modifier", [])]
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (doc_comment) @documentation.doc,
                (comment) @documentation.comment,
                (block_comment) @documentation.block
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.doc", {}).get("text", "") or
                       node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.block", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "module": {
            "pattern": """
            [
                (package_clause
                    name: (identifier) @structure.package.name) @structure.package,
                
                (import_declaration
                    importers: (import_importers
                        (importer
                            name: (_) @structure.import.name
                            selector: (import_selector)? @structure.import.selector))) @structure.import
            ]
            """,
            "extract": lambda node: {
                "package": node["captures"].get("structure.package.name", {}).get("text", ""),
                "imports": [imp.get("text", "") for imp in node["captures"].get("structure.import.name", [])]
            }
        }
    }
} 