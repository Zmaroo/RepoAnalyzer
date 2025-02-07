"""GDScript-specific Tree-sitter patterns."""

GDSCRIPT_PATTERNS = {
    # Function patterns
    "function": """
        [
          (function_definition
            name: (name) @function.name
            parameters: (parameters) @function.params
            return_type: (type)? @function.return_type
            body: (body) @function.body) @function.def,
          (constructor_definition
            parameters: (parameters) @constructor.params
            body: (body) @function.body) @constructor.def
        ]
    """,

    # Class patterns
    "class": """
        [
          (class_definition
            name: (name) @class.name
            body: (body) @class.body) @class.def,
          (class_name_statement
            name: (_) @class.declaration) @class.name_stmt,
          (extends_statement
            value: (_) @class.extends) @class.extends_stmt
        ]
    """,

    # Variable patterns
    "variable": """
        [
          (variable_statement
            name: (name) @var.name
            type: (_)? @var.type
            setget: (setget)? @var.setget) @var.def,
          (const_statement
            name: (name) @const.name
            value: (_) @const.value) @const.def,
          (export_variable_statement
            name: (name) @export.name
            type: (_)? @export.type
            value: (_)? @export.value) @export.def,
          (onready_variable_statement
            name: (name) @onready.name
            value: (_) @onready.value) @onready.def
        ]
    """,

    # Control flow patterns
    "control_flow": """
        [
          (if_statement
            condition: (_) @if.condition
            body: (body) @if.body
            alternative: (_)* @if.alternative) @if,
          (for_statement
            left: (identifier) @for.var
            right: (_) @for.iterator
            body: (body) @for.body) @for,
          (while_statement
            condition: (_) @while.condition
            body: (body) @while.body) @while,
          (match_statement
            value: (_) @match.value
            body: (_) @match.body) @match
        ]
    """,

    # Expression patterns
    "expression": """
        [
          (binary_operator
            left: (_) @expr.binary.left
            right: (_) @expr.binary.right) @expr.binary,
          (unary_operator
            operand: (_) @expr.unary.operand) @expr.unary,
          (call
            function: (_) @expr.call.func
            arguments: (_)? @expr.call.args) @expr.call,
          (base_call
            function: (_) @expr.base.func
            arguments: (_)? @expr.base.args) @expr.base
        ]
    """,

    # Node patterns
    "node": """
        [
          (get_node
            path: (_) @node.path) @node.get,
          (node_path) @node.path
        ]
    """,

    # Signal patterns
    "signal": """
        [
          (signal_statement
            name: (name) @signal.name
            parameters: (parameters)? @signal.params) @signal.def
        ]
    """,

    # Value patterns
    "value": """
        [
          (integer) @value.integer,
          (float) @value.float,
          (string) @value.string,
          (true) @value.true,
          (false) @value.false,
          (null) @value.null,
          (array) @value.array,
          (dictionary) @value.dictionary
        ]
    """,

    # Remote patterns
    "remote": """
        [
          (remote_keyword) @remote,
          (master) @remote.master,
          (puppet) @remote.puppet,
          (remotesync) @remote.sync,
          (mastersync) @remote.master_sync,
          (puppetsync) @remote.puppet_sync
        ]
    """,

    # Tool/Static patterns
    "tool": """
        [
          (tool_statement) @tool,
          (static_keyword) @static
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 