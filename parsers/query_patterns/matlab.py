"""
Query patterns for MATLAB files.
"""

from .common import COMMON_PATTERNS

MATLAB_PATTERNS = {
    "syntax": {
        "function": [
            """
            (function_definition
                name: (identifier) @name
                parameters: (parameter_list)? @params
                outputs: (output_list)? @returns
                body: (_)* @body) @function
            """
        ],
        "class": [
            """
            (classdef
                name: (identifier) @name
                properties: (properties_block)? @properties
                methods: (methods_block)? @methods) @class
            """
        ]
    },
    "structure": {
        "namespace": [
            """
            (script_file) @namespace
            """
        ],
        "import": [
            """
            (import_statement) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (assignment
                left: (identifier) @name
                right: (_) @value) @variable
            """
        ],
        "expression": [
            """
            (function_call
                name: (identifier) @name
                arguments: (argument_list) @args) @expression
            """
        ]
    },
    "documentation": {
        "docstring": [
            """
            (comment
                (comment_content) @content
                (#match? @content "^%{")) @docstring
            """
        ],
        "comment": [
            """
            (comment) @comment
            """
        ]
    },
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_definition) @syntax.function,
          
          ; Rich function patterns
          (function_definition
            outputs: (output_parameters
              parameters: [(identifier) @syntax.function.output.name]*) @syntax.function.outputs
            name: (identifier) @syntax.function.name
            inputs: (input_parameters
              parameters: [(identifier) @syntax.function.param.name
                         (validation_parameters
                           class: (identifier) @syntax.function.param.class
                           attributes: (attribute_list)? @syntax.function.param.attrs)]*) @syntax.function.params
            body: (block) @syntax.function.body) @syntax.function.def,
            
          ; Nested function patterns
          (nested_function
            outputs: (output_parameters)? @syntax.function.nested.outputs
            name: (identifier) @syntax.function.nested.name
            inputs: (input_parameters)? @syntax.function.nested.params
            body: (block) @syntax.function.nested.body) @syntax.function.nested,
            
          ; Anonymous function patterns
          (lambda
            parameters: (parameter_list
              parameters: (identifier)* @syntax.function.lambda.param)? @syntax.function.lambda.params
            body: (_) @syntax.function.lambda.body) @syntax.function.lambda
        ]
    """,
    
    # Class patterns
    "class": """
        [
          (classdef
            attributes: (attribute_list
              [(identifier) @syntax.class.attr.name
               (attribute
                 name: (identifier) @syntax.class.attr.name
                 value: (_) @syntax.class.attr.value)]*) @syntax.class.attributes
            name: (identifier) @syntax.class.name
            superclasses: (superclass_list
              classes: (identifier)* @syntax.class.superclass)? @syntax.class.inheritance
            body: (block
              [(property_block
                 attributes: (attribute_list)? @syntax.class.property.attributes
                 definitions: (property_list
                   properties: [(identifier) @syntax.class.property.name]*) @syntax.class.property.list) @syntax.class.property
               (methods_block
                 attributes: (attribute_list)? @syntax.class.methods.attributes
                 definitions: (function_list
                   functions: [(function_definition) @syntax.class.method]*) @syntax.class.methods.list) @syntax.class.methods
               (events_block
                 attributes: (attribute_list)? @syntax.class.events.attributes
                 definitions: (event_list
                   events: [(identifier) @syntax.class.event.name]*) @syntax.class.events.list) @syntax.class.events]*) @syntax.class.body) @syntax.class.def
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          (script_file
            name: (identifier) @structure.script.name) @structure.script,
            
          (function_file
            function: (function_definition) @structure.function.def) @structure.function
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Help text
          (comment) @documentation.help {
            match: "^%[%\\s]"
          },
          
          ; Documentation sections
          (comment) @documentation.section {
            match: "^%\\s*[A-Z][A-Za-z\\s]+:?"
          },
          
          ; See also references
          (comment) @documentation.seealso {
            match: "^%\\s*See also:"
          }
        ]
    """,
    
    # Array patterns
    "array": """
        [
          (array
            elements: [(number) @semantics.array.number
                      (string) @semantics.array.string
                      (identifier) @semantics.array.variable
                      (operator) @semantics.array.operator]*) @semantics.array,
                      
          (cell_array
            elements: (_)* @semantics.cell.elements) @semantics.cell,
                      
          (array_indexing
            array: (_) @semantics.array.index.array
            indices: (index_list
              indices: (_)* @semantics.array.index.expr)) @semantics.array.index
        ]
    """,
    
    # Control flow patterns
    "control": """
        [
          (for_loop
            iterator: (identifier) @semantics.control.for.iterator
            range: (_) @semantics.control.for.range
            body: (block) @semantics.control.for.body) @semantics.control.for,
            
          (while_loop
            condition: (_) @semantics.control.while.condition
            body: (block) @semantics.control.while.body) @semantics.control.while,
            
          (if_statement
            condition: (_) @semantics.control.if.condition
            body: (block) @semantics.control.if.body
            elseif_clauses: (elseif_clause
              condition: (_) @semantics.control.elseif.condition
              body: (block) @semantics.control.elseif.body)*
            else_clause: (else_clause
              body: (block) @semantics.control.else.body)?) @semantics.control.if,
              
          (try_statement
            body: (block) @semantics.control.try.body
            catch_clause: (catch_clause
              identifier: (identifier)? @semantics.control.catch.error
              body: (block) @semantics.control.catch.body)?) @semantics.control.try
        ]
    """,
    
    # Graphics patterns
    "graphics": """
        [
          (function_call
            function: (identifier) @semantics.graphics.func
            (#match? @semantics.graphics.func "^(plot|figure|subplot|surf|mesh|imagesc)$")
            arguments: (argument_list) @semantics.graphics.args) @semantics.graphics.call,
            
          (handle
            type: (identifier) @semantics.graphics.handle.type
            properties: (property_list
              properties: [(property_assignment
                           name: (identifier) @semantics.graphics.handle.prop.name
                           value: (_) @semantics.graphics.handle.prop.value)]*) @semantics.graphics.handle.props) @semantics.graphics.handle
        ]
    """
} 