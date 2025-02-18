"""Lua-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

LUA_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    # Syntax category with rich patterns
    "function": """
        [
          ; Basic function (from common)
          (function_declaration) @syntax.function,
          
          ; Rich function patterns
          (function_declaration
            name: [(identifier) @syntax.function.name
                  (dot_index_expression
                    table: (identifier) @syntax.function.table
                    field: (identifier) @syntax.function.field)
                  (method_index_expression
                    table: (identifier) @syntax.function.class
                    method: (identifier) @syntax.function.method)]
            parameters: (parameters
              [(identifier) @syntax.function.param.name
               (spread) @syntax.function.param.varargs]*) @syntax.function.params
            body: (block) @syntax.function.body) @syntax.function.def,
            
          ; Local function patterns
          (local_function
            name: (identifier) @syntax.function.local.name
            parameters: (parameters) @syntax.function.local.params
            body: (block) @syntax.function.local.body) @syntax.function.local,
            
          ; Method patterns
          (function_declaration
            name: (method_index_expression) @syntax.function.method.name) @syntax.function.method
        ]
    """,
    
    # Table patterns
    "table": """
        [
          (table_constructor
            [(field
               name: (identifier) @syntax.table.field.name
               value: (_) @syntax.table.field.value)
             (bracket_field
               key: (_) @syntax.table.field.key
               value: (_) @syntax.table.field.value)]*) @syntax.table,
               
          ; Metatables
          (assignment_statement
            variables: (variable_list
              (identifier) @syntax.table.meta.table)
            values: (expression_list
              (function_call
                prefix: (identifier) @syntax.table.meta.func
                (#match? @syntax.table.meta.func "^setmetatable$")))) @syntax.table.meta
        ]
    """,
    
    # Structure category with rich patterns
    "module": """
        [
          (assignment_statement
            variables: (variable_list
              (identifier) @structure.module.name)
            values: (expression_list
              (table_constructor) @structure.module.exports)) @structure.module,
              
          (function_call
            prefix: (identifier) @structure.require.func
            (#match? @structure.require.func "^require$")
            arguments: (arguments
              (string) @structure.require.path)) @structure.require
        ]
    """,
    
    # Object-oriented patterns
    "class": """
        [
          ; Class definition
          (assignment_statement
            variables: (variable_list
              (identifier) @syntax.class.name)
            values: (expression_list
              (table_constructor
                [(field
                   name: (identifier) @syntax.class.method.name
                   value: (function_definition) @syntax.class.method.def)
                 (field
                   name: (identifier) @syntax.class.field.name
                   value: (_) @syntax.class.field.value)]*) @syntax.class.body)) @syntax.class.def,
                   
          ; Inheritance
          (function_call
            prefix: (identifier) @syntax.class.inherit.func
            (#match? @syntax.class.inherit.func "^setmetatable$")
            arguments: (arguments
              [(identifier) @syntax.class.child
               (table_constructor
                 (field
                   name: (identifier) @syntax.class.meta.index
                   (#match? @syntax.class.meta.index "^__index$")
                   value: (identifier) @syntax.class.parent))]*)) @syntax.class.inherit
        ]
    """,
    
    # Documentation category with rich patterns
    "documentation": """
        [
          ; Basic comments (from common)
          (comment) @documentation.comment,
          
          ; LuaDoc patterns
          (comment) @documentation.luadoc {
            match: "^---"
          },
          
          ; LuaDoc tags
          (comment) @documentation.luadoc.tag {
            match: "@[a-zA-Z]+"
          }
        ]
    """,
    
    # Error handling patterns
    "error": """
        [
          (function_call
            prefix: (identifier) @semantics.error.func
            (#match? @semantics.error.func "^(error|assert)$")
            arguments: (arguments
              (_) @semantics.error.message)) @semantics.error.raise,
              
          (function_call
            prefix: (identifier) @semantics.error.pcall
            (#match? @semantics.error.pcall "^(pcall|xpcall)$")
            arguments: (arguments
              (_) @semantics.error.protected)) @semantics.error.protect
        ]
    """,
    
    # Coroutine patterns
    "coroutine": """
        [
          (function_call
            prefix: (dot_index_expression
              table: (identifier) @semantics.coroutine.module
              (#match? @semantics.coroutine.module "^coroutine$")
              field: (identifier) @semantics.coroutine.func
              (#match? @semantics.coroutine.func "^(create|resume|yield|status|wrap)$"))
            arguments: (arguments
              (_)* @semantics.coroutine.args)) @semantics.coroutine.call
        ]
    """
} 