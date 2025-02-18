"""JavaScript-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS
from .js_base import JS_BASE_PATTERNS

JAVASCRIPT_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    **JS_BASE_PATTERNS,  # Include JavaScript base patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            modifiers: [(async) (export) (default)]* @syntax.function.modifier
            name: (identifier) @syntax.function.name
            parameters: (formal_parameters
              [(identifier) @syntax.function.param.name
               (assignment_pattern
                 left: (identifier) @syntax.function.param.name
                 right: (_) @syntax.function.param.default)
               (rest_pattern
                 name: (identifier) @syntax.function.param.rest)
               (object_pattern
                 (shorthand_property_identifier_pattern) @syntax.function.param.destructure.object)
               (array_pattern
                 (identifier) @syntax.function.param.destructure.array)]*) @syntax.function.params
            body: (statement_block) @syntax.function.body) @syntax.function.def,
            
          ; Arrow function patterns
          (arrow_function
            modifiers: (async)? @syntax.function.arrow.modifier
            parameters: (formal_parameters) @syntax.function.arrow.params
            body: [(statement_block) (expression)] @syntax.function.arrow.body) @syntax.function.arrow,
            
          ; Method patterns
          (method_definition
            modifiers: [(static) (async) (get) (set)]* @syntax.function.method.modifier
            name: [(property_identifier) (computed_property_name)] @syntax.function.method.name
            parameters: (formal_parameters) @syntax.function.method.params
            body: (statement_block) @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    "class": """
        [
          ; Basic class (from common)
          (class_declaration) @syntax.class,
          
          ; Rich class patterns
          (class_declaration
            modifiers: [(export) (default)]* @syntax.class.modifier
            name: (identifier) @syntax.class.name
            extends: (class_heritage
              (extends_clause
                value: (_) @syntax.class.extends.value)?) @syntax.class.extends
            body: (class_body
              [(method_definition) @syntax.class.method
               (field_definition
                 modifiers: [(static) (private)]* @syntax.class.field.modifier
                 property: [(property_identifier) (private_property_identifier)] @syntax.class.field.name
                 value: (_)? @syntax.class.field.value) @syntax.class.field
               (class_static_block) @syntax.class.static_block]*) @syntax.class.body) @syntax.class.def
        ]
    """,
    
    # Module system patterns
    "module": """
        [
          ; Basic import/export (from common)
          (import_statement) @structure.import,
          (export_statement) @structure.export,
          
          ; Rich import patterns
          (import_statement
            imports: [(import_clause
                       [(namespace_import
                         name: (identifier) @structure.import.namespace)
                        (named_imports
                          (import_specifier
                            name: (identifier) @structure.import.name
                            alias: (identifier)? @structure.import.alias)*)])
                     (identifier) @structure.import.default] @structure.import.clause
            source: (string) @structure.import.source) @structure.import,
            
          ; Rich export patterns
          (export_statement
            declaration: (_)? @structure.export.declaration
            exports: (export_clause
              (export_specifier
                name: (identifier) @structure.export.name
                alias: (identifier)? @structure.export.alias)*)? @structure.export.clause
            source: (string)? @structure.export.source) @structure.export
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (comment) @documentation.comment,
          
          ; JSDoc patterns
          (comment
            text: /\\/\\*\\*.*?\\*\\// @documentation.jsdoc.block) @documentation.jsdoc,
            
          ; JSDoc tags
          (comment
            text: /@[a-zA-Z]+.*/) @documentation.jsdoc.tag
        ]
    """,
    
    # Modern JavaScript features
    "modern": """
        [
          ; Nullish coalescing
          (binary_expression
            left: (_) @semantics.nullish.left
            operator: "??"
            right: (_) @semantics.nullish.right) @semantics.nullish,
            
          ; Optional chaining
          (member_expression
            object: (_) @semantics.optional_chain.object
            optional: "?."
            property: (_) @semantics.optional_chain.property) @semantics.optional_chain,
            
          ; Private class features
          (private_property_identifier) @semantics.private.property,
          (private_property_definition) @semantics.private.definition,
            
          ; Class fields
          (field_definition) @semantics.class_field,
          (class_static_block) @semantics.static_block
        ]
    """,
    
    # Async patterns
    "async": """
        [
          (await_expression
            value: (_) @semantics.async.await.value) @semantics.async.await,
            
          (function_declaration
            modifiers: (async) @semantics.async.function.modifier) @semantics.async.function,
            
          (method_definition
            modifiers: (async) @semantics.async.method.modifier) @semantics.async.method,
            
          (arrow_function
            modifiers: (async) @semantics.async.arrow.modifier) @semantics.async.arrow
        ]
    """,
    
    # JavaScript-specific patterns
    "jsx": """
        [
          (jsx_element
            opening_element: (jsx_opening_element
              name: (_) @syntax.jsx.tag.name
              attributes: (jsx_attributes
                (jsx_attribute
                  name: (jsx_attribute_name) @syntax.jsx.attr.name
                  value: (_)? @syntax.jsx.attr.value)*)?
            ) @syntax.jsx.open
            children: (_)* @syntax.jsx.children
            closing_element: (jsx_closing_element)? @syntax.jsx.close
          ) @syntax.jsx.element,
          
          (jsx_self_closing_element
            name: (_) @syntax.jsx.self.name
            attributes: (jsx_attributes
              (jsx_attribute
                name: (jsx_attribute_name) @syntax.jsx.self.attr.name
                value: (_)? @syntax.jsx.self.attr.value)*)?
          ) @syntax.jsx.self
        ]
    """,
    
    "dynamic_import": """
        [
          (call_expression
            function: (import) @syntax.import.dynamic
            arguments: (arguments
              (string) @syntax.import.source)) @syntax.import.dynamic_call
        ]
    """,
    
    "class_fields": """
        [
          (field_definition
            name: (property_identifier) @syntax.class.field.name
            value: (_)? @syntax.class.field.value) @syntax.class.field,
          (private_field_definition
            name: (private_property_identifier) @syntax.class.field.private.name
            value: (_)? @syntax.class.field.private.value) @syntax.class.field.private
        ]
    """
} 