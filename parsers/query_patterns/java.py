"""Java-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

JAVA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic method (from common)
          (method_declaration) @syntax.method,
          
          ; Rich method patterns
          (method_declaration
            modifiers: [(public) (private) (protected) (static) (final) (abstract) (synchronized)]* @syntax.function.modifier
            type_parameters: (type_parameters
              (type_parameter
                name: (identifier) @syntax.function.type_param.name
                bounds: (type_bound)? @syntax.function.type_param.bound)*) @syntax.function.type_params
            type: (_) @syntax.function.return_type
            name: (identifier) @syntax.function.name
            parameters: (formal_parameters
              (formal_parameter
                modifiers: [(final)]* @syntax.function.param.modifier
                type: (_) @syntax.function.param.type
                name: (identifier) @syntax.function.param.name
                dimensions: (dimensions)? @syntax.function.param.array)*) @syntax.function.params
            dimensions: (dimensions)? @syntax.function.array
            throws: (throws
              types: (type_list)? @syntax.function.throws.types)? @syntax.function.throws
            body: (block)? @syntax.function.body) @syntax.function.def,
            
          ; Constructor patterns
          (constructor_declaration
            modifiers: [(public) (private) (protected)]* @syntax.function.constructor.modifier
            name: (identifier) @syntax.function.constructor.name
            parameters: (formal_parameters) @syntax.function.constructor.params
            throws: (throws)? @syntax.function.constructor.throws
            body: (constructor_body
              (explicit_constructor_invocation)? @syntax.function.constructor.super
              (block)? @syntax.function.constructor.block) @syntax.function.constructor.body) @syntax.function.constructor
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            modifiers: [(public) (private) (protected) (static) (final) (abstract)]* @syntax.class.modifier
            name: (identifier) @syntax.class.name
            type_parameters: (type_parameters)? @syntax.class.type_params
            superclass: (superclass
              type: (_) @syntax.class.extends.type)? @syntax.class.extends
            interfaces: (super_interfaces
              types: (type_list)? @syntax.class.implements.types)? @syntax.class.implements
            body: (class_body
              [(field_declaration) @syntax.class.field
               (method_declaration) @syntax.class.method
               (constructor_declaration) @syntax.class.constructor
               (static_initializer) @syntax.class.static_init
               (class_declaration) @syntax.class.nested]*) @syntax.class.body) @syntax.class.def,
               
          ; Interface patterns
          (interface_declaration
            modifiers: [(public) (private) (protected) (static) (abstract)]* @syntax.interface.modifier
            name: (identifier) @syntax.interface.name
            type_parameters: (type_parameters)? @syntax.interface.type_params
            extends_interfaces: (extends_interfaces
              types: (type_list)? @syntax.interface.extends.types)? @syntax.interface.extends
            body: (interface_body
              [(constant_declaration) @syntax.interface.constant
               (method_declaration) @syntax.interface.method]*) @syntax.interface.body) @syntax.interface.def
        ]
    """,
    
    # Structure category with rich patterns
    "package": """
        [
          ; Basic package (from common)
          (package_declaration) @structure.package,
          
          ; Rich package patterns
          (package_declaration
            name: (scoped_identifier
              scope: (identifier)* @structure.package.scope
              name: (identifier) @structure.package.name)) @structure.package.def,
              
          (import_declaration
            static: (static_import)? @structure.import.static
            name: (scoped_identifier) @structure.import.name
            asterisk: (asterisk)? @structure.import.wildcard) @structure.import
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (line_comment) @documentation.comment.line,
          (block_comment) @documentation.comment.block,
          
          ; Javadoc patterns
          (javadoc_comment
            (javadoc_tag
              name: (_) @documentation.javadoc.tag.name
              description: (_)? @documentation.javadoc.tag.description)*) @documentation.javadoc,
              
          ; Documentation tags
          (javadoc_tag
            text: /@[a-zA-Z]+.*/) @documentation.tag
        ]
    """,
    
    # Annotation patterns
    "annotation": """
        [
          (annotation
            name: (identifier) @semantics.annotation.name
            arguments: (annotation_argument_list
              (annotation_argument
                name: (identifier)? @semantics.annotation.arg.name
                value: (_) @semantics.annotation.arg.value)*) @semantics.annotation.args) @semantics.annotation,
                
          (marker_annotation
            name: (identifier) @semantics.annotation.marker) @semantics.annotation.marker
        ]
    """,
    
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