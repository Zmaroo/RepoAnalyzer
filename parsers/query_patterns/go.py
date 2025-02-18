"""Go-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

GO_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            name: (identifier) @syntax.function.name
            type_parameters: (type_parameter_list
              (type_parameter
                name: (identifier) @syntax.function.type_param.name
                type: (type_spec)? @syntax.function.type_param.constraint)*) @syntax.function.type_params
            parameters: (parameter_list
              [(parameter_declaration
                 name: (identifier) @syntax.function.param.name
                 type: (_) @syntax.function.param.type)
               (variadic_parameter_declaration
                 name: (identifier) @syntax.function.param.name
                 type: (_) @syntax.function.param.type)]*) @syntax.function.params
            result: [(type_identifier) (parameter_list)]? @syntax.function.return_type
            body: (block) @syntax.function.body) @syntax.function.def,
            
          ; Method patterns
          (method_declaration
            receiver: (parameter_list
              (parameter_declaration
                name: (identifier)? @syntax.function.method.receiver.name
                type: (_) @syntax.function.method.receiver.type)) @syntax.function.method.receiver
            name: (identifier) @syntax.function.method.name
            parameters: (parameter_list) @syntax.function.method.params
            result: (_)? @syntax.function.method.return_type
            body: (block) @syntax.function.method.body) @syntax.function.method
        ]
    """,
    
    "type": """
        [
          ; Basic type (from common)
          (type_declaration) @syntax.type,
          
          ; Rich type patterns
          (type_declaration
            name: (type_identifier) @syntax.type.name
            type: [(struct_type
                    fields: (field_declaration_list
                      [(field_declaration
                         name: (field_identifier) @syntax.type.struct.field.name
                         type: (_) @syntax.type.struct.field.type
                         tag: (raw_string_literal)? @syntax.type.struct.field.tag)
                       (embedded_field
                         type: (_) @syntax.type.struct.embed.type)]*) @syntax.type.struct.fields) @syntax.type.struct
                   (interface_type
                     methods: (method_spec_list
                       [(method_spec
                          name: (identifier) @syntax.type.interface.method.name
                          parameters: (parameter_list) @syntax.type.interface.method.params
                          result: (_)? @syntax.type.interface.method.return_type)
                        (type_identifier) @syntax.type.interface.embed]*) @syntax.type.interface.methods) @syntax.type.interface]) @syntax.type.def
        ]
    """,
    
    # Structure category with rich patterns
    "package": """
        [
          ; Basic package (from common)
          (package_clause) @structure.package,
          
          ; Rich package patterns
          (package_clause
            name: (identifier) @structure.package.name) @structure.package.def,
            
          (import_declaration
            specs: (import_spec_list
              (import_spec
                name: (identifier)? @structure.import.alias
                path: (interpreted_string_literal) @structure.import.path)*) @structure.import.specs) @structure.import
        ]
    """,
    
    # Concurrency patterns
    "concurrency": """
        [
          ; Goroutines
          (go_expression
            expression: (_) @semantics.concurrency.go.expr) @semantics.concurrency.go,
            
          ; Channels
          (channel_type
            value: (_) @semantics.concurrency.chan.type) @semantics.concurrency.chan,
            
          (send_statement
            channel: (_) @semantics.concurrency.send.channel
            value: (_) @semantics.concurrency.send.value) @semantics.concurrency.send,
            
          (receive_expression
            channel: (_) @semantics.concurrency.receive.channel) @semantics.concurrency.receive,
            
          ; Select
          (select_statement
            body: (communication_case
              communication: (_) @semantics.concurrency.select.comm
              body: (_) @semantics.concurrency.select.body)*) @semantics.concurrency.select
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; Rich documentation patterns
          (comment) @documentation.comment,
          
          ; Godoc patterns
          (comment
            text: /\\/\\/\\s*[A-Z].*/) @documentation.godoc.line,
            
          (comment
            text: /\\/\\*\\s*[A-Z].*?\\*\\// @documentation.godoc.block)
        ]
    """,
    
    # Testing patterns
    "testing": """
        [
          (function_declaration
            name: (identifier) @semantics.test.name
            (#match? @semantics.test.name "^Test")
            parameters: (parameter_list
              (parameter_declaration
                type: (type_identifier) @semantics.test.param.type
                (#match? @semantics.test.param.type "^\\*?testing\\.T$"))) @semantics.test.function,
                
          (call_expression
            function: (selector_expression
              operand: (identifier)
              field: (identifier) @semantics.test.method
              (#match? @semantics.test.method "^(Error|Fatal|Log)"))
            arguments: (argument_list) @semantics.test.args) @semantics.test.call
        ]
    """,
    
    # Error handling patterns
    "error": """
        [
          (if_statement
            condition: (binary_expression
              left: (_) @semantics.error.check.value
              operator: "!="
              right: (identifier) @semantics.error.check.nil
              (#match? @semantics.error.check.nil "^nil$")) @semantics.error.check
            consequence: (block) @semantics.error.handle) @semantics.error.if,
            
          (type_assertion_expression
            type: (type_identifier) @semantics.error.type
            (#match? @semantics.error.type "^error$")) @semantics.error.assert
        ]
    """
} 