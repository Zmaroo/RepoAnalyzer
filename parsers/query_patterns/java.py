"""Java-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

JAVA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "syntax": {
        "function": {
            "pattern": """
            [
                (method_declaration
                    modifiers: (_)* @syntax.function.modifier
                    type_parameters: (type_parameters)? @syntax.function.type_params
                    type: (_) @syntax.function.return_type
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters) @syntax.function.params
                    dimensions: (dimensions)? @syntax.function.dimensions
                    throws: (throws)? @syntax.function.throws
                    body: (block)? @syntax.function.body) @syntax.function.method,
                
                (constructor_declaration
                    modifiers: (_)* @syntax.function.constructor.modifier
                    name: (identifier) @syntax.function.constructor.name
                    parameters: (formal_parameters) @syntax.function.constructor.params
                    throws: (throws)? @syntax.function.constructor.throws
                    body: (constructor_body) @syntax.function.constructor.body) @syntax.function.constructor
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                "return_type": node["captures"].get("syntax.function.return_type", {}).get("text", ""),
                "parameters": node["captures"].get("syntax.function.params", {}).get("text", ""),
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.function.modifier", [])],
                "type_params": node["captures"].get("syntax.function.type_params", {}).get("text", ""),
                "throws": node["captures"].get("syntax.function.throws", {}).get("text", "")
            }
        },
        "class": {
            "pattern": """
            [
                (class_declaration
                    modifiers: (_)* @syntax.class.modifier
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameters)? @syntax.class.type_params
                    superclass: (superclass)? @syntax.class.superclass
                    interfaces: (super_interfaces)? @syntax.class.interfaces
                    permits: (permits)? @syntax.class.permits
                    body: (class_body) @syntax.class.body) @syntax.class.def,
                
                (interface_declaration
                    modifiers: (_)* @syntax.interface.modifier
                    name: (identifier) @syntax.interface.name
                    type_parameters: (type_parameters)? @syntax.interface.type_params
                    interfaces: (extends_interfaces)? @syntax.interface.extends
                    permits: (permits)? @syntax.interface.permits
                    body: (interface_body) @syntax.interface.body) @syntax.interface.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.class.name", {}).get("text", "") or 
                       node["captures"].get("syntax.interface.name", {}).get("text", ""),
                "type": "class" if "syntax.class.name" in node["captures"] else "interface",
                "modifiers": [m.text.decode('utf8') for m in node["captures"].get("syntax.class.modifier", []) or 
                            node["captures"].get("syntax.interface.modifier", [])],
                "superclass": node["captures"].get("syntax.class.superclass", {}).get("text", ""),
                "interfaces": node["captures"].get("syntax.class.interfaces", {}).get("text", "") or
                            node["captures"].get("syntax.interface.extends", {}).get("text", "")
            }
        }
    },
    
    # Structure category with rich patterns
    "structure": {
        "package": {
            "pattern": """
            [
                (package_declaration
                    name: (_) @structure.package.name) @structure.package,
                
                (import_declaration
                    name: (_) @structure.import.name
                    static: (_)? @structure.import.static
                    asterisk: (_)? @structure.import.wildcard) @structure.import
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("structure.package.name", {}).get("text", ""),
                "imports": [i.text.decode('utf8') for i in node["captures"].get("structure.import.name", [])]
            }
        }
    },
    
    # Documentation category with rich patterns
    "documentation": {
        "comment": {
            "pattern": """
            [
                (line_comment) @documentation.line,
                (block_comment) @documentation.block
            ]
            """,
            "extract": lambda node: {
                "text": node["node"].text.decode('utf8'),
                "type": "line" if node["node"].type == "line_comment" else "block",
                "is_javadoc": node["node"].text.decode('utf8').startswith('/**')
            }
        }
    },
    
    # Annotation patterns
    "semantics": {
        "annotation": {
            "pattern": """
            [
                (annotation
                    name: (identifier) @semantics.annotation.name
                    arguments: (annotation_argument_list)? @semantics.annotation.args) @semantics.annotation,
                
                (marker_annotation
                    name: (identifier) @semantics.annotation.marker.name) @semantics.annotation.marker
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.annotation.name", {}).get("text", "") or
                       node["captures"].get("semantics.annotation.marker.name", {}).get("text", ""),
                "arguments": node["captures"].get("semantics.annotation.args", {}).get("text", ""),
                "type": "marker" if "semantics.annotation.marker.name" in node["captures"] else "normal"
            }
        }
    },
    
    # Spring Framework patterns
    "spring": """
        [
          (annotation
            name: (identifier) @semantics.spring.annotation
            (#match? @semantics.spring.annotation "^(Controller|Service|Repository|Component|Autowired|Configuration)$")
            arguments: (annotation_argument_list)? @semantics.spring.args) @semantics.spring.component,
            
          (annotation
            name: (identifier) @semantics.spring.mapping
            (#match? @semantics.spring.mapping "^(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)$")
            arguments: (annotation_argument_list)? @semantics.spring.mapping.args) @semantics.spring.endpoint
        ]
    """
} 