"""Query patterns for Svelte files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

SVELTE_PATTERNS_FOR_LEARNING = {
    "component_structure": {
        "pattern": """
        [
            (script_element
                attribute: (attribute)* @component.script.attrs
                content: [(javascript_program) (typescript_program)]? @component.script.content) @component.script,
                
            (style_element
                attribute: (attribute)* @component.style.attrs
                content: (_)? @component.style.content) @component.style,
                
            (element
                name: (tag_name) @component.custom.name {
                    match: "^[A-Z].*"
                }
                attribute: (attribute)* @component.custom.attrs
                body: (_)* @component.custom.body) @component.custom,
                
            (element
                name: (tag_name) @component.slot.name {
                    match: "^slot$"
                }
                attribute: (attribute
                    name: (attribute_name) @component.slot.attr.name
                    value: (attribute_value) @component.slot.attr.value)* @component.slot.attrs
                body: (_)* @component.slot.body) @component.slot
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "component_structure",
            "is_script": "component.script" in node["captures"],
            "is_style": "component.style" in node["captures"],
            "is_custom_component": "component.custom" in node["captures"],
            "is_slot": "component.slot" in node["captures"],
            "has_typescript": "component.script" in node["captures"] and "typescript_program" in node["captures"].get("component.script.content", {}).get("type", ""),
            "script_attrs": [attr.get("text", "") for attr in node["captures"].get("component.script.attrs", [])],
            "style_attrs": [attr.get("text", "") for attr in node["captures"].get("component.style.attrs", [])],
            "component_name": node["captures"].get("component.custom.name", {}).get("text", ""),
            "slot_name": node["captures"].get("component.slot.attr.value", {}).get("text", "default"),
            "component_type": (
                "script" if "component.script" in node["captures"] else
                "style" if "component.style" in node["captures"] else
                "custom_component" if "component.custom" in node["captures"] else
                "slot" if "component.slot" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "reactivity": {
        "pattern": """
        [
            (raw_text_expr) @reactivity.expr,
            
            (if_block
                expression: (_) @reactivity.if.cond
                consequence: (_) @reactivity.if.then
                alternative: (_)? @reactivity.if.else) @reactivity.if,
                
            (each_block
                expression: (_) @reactivity.each.expr
                context: (each_block_context
                    name: (_) @reactivity.each.item
                    index: (_)? @reactivity.each.index)? @reactivity.each.ctx
                body: (_) @reactivity.each.body
                else_clause: (_)? @reactivity.each.empty) @reactivity.each,
                
            (await_block
                expression: (_) @reactivity.await.expr
                pending: (_)? @reactivity.await.pending
                fulfilled: (_)? @reactivity.await.then
                rejected: (_)? @reactivity.await.catch) @reactivity.await
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "reactivity",
            "is_expression": "reactivity.expr" in node["captures"],
            "is_if_block": "reactivity.if" in node["captures"],
            "is_each_block": "reactivity.each" in node["captures"],
            "is_await_block": "reactivity.await" in node["captures"],
            "expression": node["captures"].get("reactivity.expr", {}).get("text", ""),
            "condition": node["captures"].get("reactivity.if.cond", {}).get("text", ""),
            "iteration_expr": node["captures"].get("reactivity.each.expr", {}).get("text", ""),
            "item_name": node["captures"].get("reactivity.each.item", {}).get("text", ""),
            "has_else": (
                ("reactivity.if" in node["captures"] and "reactivity.if.else" in node["captures"] and node["captures"].get("reactivity.if.else", {}).get("text", "") != "") or
                ("reactivity.each" in node["captures"] and "reactivity.each.empty" in node["captures"] and node["captures"].get("reactivity.each.empty", {}).get("text", "") != "")
            ),
            "reactivity_type": (
                "expression" if "reactivity.expr" in node["captures"] else
                "if_block" if "reactivity.if" in node["captures"] else
                "each_block" if "reactivity.each" in node["captures"] else
                "await_block" if "reactivity.await" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "state_management": {
        "pattern": """
        [
            (lexical_declaration
                declarator: (variable_declarator
                    name: (identifier) @state.var.name
                    value: (call_expression
                        function: (identifier) @state.var.func {
                            match: "^(writable|readable|derived)$"
                        }
                        arguments: (arguments) @state.var.args) @state.var.init) @state.var.decl) @state.var,
                
            (assignment_expression
                left: (member_expression
                    object: (_) @state.update.obj
                    property: (property_identifier) @state.update.prop {
                        match: "^(set|update)$"
                    }) @state.update.target
                right: (_) @state.update.value) @state.update,
                
            (call_expression
                function: (member_expression
                    object: (identifier) @state.call.obj
                    property: (property_identifier) @state.call.method {
                        match: "^(set|update|subscribe|invalidate)$"
                    }) @state.call.func
                arguments: (arguments) @state.call.args) @state.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "state_management",
            "is_store_declaration": "state.var" in node["captures"],
            "is_store_update": "state.update" in node["captures"],
            "is_store_method_call": "state.call" in node["captures"],
            "store_name": node["captures"].get("state.var.name", {}).get("text", ""),
            "store_type": node["captures"].get("state.var.func", {}).get("text", ""),
            "update_target": node["captures"].get("state.update.obj", {}).get("text", ""),
            "update_method": node["captures"].get("state.update.prop", {}).get("text", ""),
            "call_target": node["captures"].get("state.call.obj", {}).get("text", ""),
            "call_method": node["captures"].get("state.call.method", {}).get("text", ""),
            "state_operation": (
                "store_declaration" if "state.var" in node["captures"] else
                "store_update" if "state.update" in node["captures"] else
                "store_method_call" if "state.call" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "event_handling": {
        "pattern": """
        [
            (attribute
                name: (attribute_name) @event.attr.name {
                    match: "^(on:[a-zA-Z]+)$"
                }
                value: (attribute_value) @event.attr.value) @event.attr,
                
            (attribute
                name: (attribute_name) @event.action.name {
                    match: "^(use:[a-zA-Z]+)$"
                }
                value: (attribute_value) @event.action.value) @event.action,
                
            (lexical_declaration
                declarator: (variable_declarator
                    name: (identifier) @event.dispatcher.name
                    value: (call_expression
                        function: (identifier) @event.dispatcher.func {
                            match: "^(createEventDispatcher)$"
                        }) @event.dispatcher.init) @event.dispatcher.decl) @event.dispatcher,
                
            (call_expression
                function: (identifier) @event.dispatch.func {
                    match: "^(dispatch)$"
                }
                arguments: (arguments
                    (string) @event.dispatch.name) @event.dispatch.args) @event.dispatch
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "event_handling",
            "is_event_handler": "event.attr" in node["captures"],
            "is_action_directive": "event.action" in node["captures"],
            "is_dispatcher_creation": "event.dispatcher" in node["captures"],
            "is_event_dispatch": "event.dispatch" in node["captures"],
            "event_name": node["captures"].get("event.attr.name", {}).get("text", ""),
            "action_name": node["captures"].get("event.action.name", {}).get("text", ""),
            "dispatcher_name": node["captures"].get("event.dispatcher.name", {}).get("text", ""),
            "dispatched_event": node["captures"].get("event.dispatch.name", {}).get("text", ""),
            "event_type": (
                "event_handler" if "event.attr" in node["captures"] else
                "action_directive" if "event.action" in node["captures"] else
                "dispatcher_creation" if "event.dispatcher" in node["captures"] else
                "event_dispatch" if "event.dispatch" in node["captures"] else
                "unknown"
            )
        }
    }
}

SVELTE_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "script": {
            "pattern": """
            (script_element
                attribute: (attribute
                    name: (attribute_name) @syntax.script.attribute.name
                    value: (attribute_value) @syntax.script.attribute.value)* @syntax.script.attributes
                content: (_)? @syntax.script.content) @syntax.script
            """,
            "extract": lambda node: {
                "attributes": {
                    attr.get("name", {}).get("text", ""): attr.get("value", {}).get("text", "")
                    for attr in node["captures"].get("syntax.script.attributes", [])
                },
                "has_content": "syntax.script.content" in node["captures"] and node["captures"].get("syntax.script.content", {}).get("text", "") != ""
            }
        },
        
        "style": {
            "pattern": """
            (style_element
                attribute: (attribute
                    name: (attribute_name) @syntax.style.attribute.name
                    value: (attribute_value) @syntax.style.attribute.value)* @syntax.style.attributes
                content: (_)? @syntax.style.content) @syntax.style
            """,
            "extract": lambda node: {
                "attributes": {
                    attr.get("name", {}).get("text", ""): attr.get("value", {}).get("text", "")
                    for attr in node["captures"].get("syntax.style.attributes", [])
                },
                "has_content": "syntax.style.content" in node["captures"] and node["captures"].get("syntax.style.content", {}).get("text", "") != ""
            }
        }
    },
    
    "semantics": {
        "component": {
            "pattern": """
            (element
                name: (tag_name) @semantics.component.name
                attribute: (attribute
                    name: (attribute_name) @semantics.component.attribute.name
                    value: (attribute_value) @semantics.component.attribute.value)* @semantics.component.attributes
                body: (_)* @semantics.component.body) @semantics.component
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.component.name", {}).get("text", ""),
                "attributes": {
                    attr.get("name", {}).get("text", ""): attr.get("value", {}).get("text", "")
                    for attr in node["captures"].get("semantics.component.attributes", [])
                }
            }
        }
    },
    
    "structure": {
        "directive": {
            "pattern": """
            [
                (if_block
                    expression: (_) @structure.if.expression
                    consequence: (_) @structure.if.consequence
                    alternative: (_)? @structure.if.alternative) @structure.if,
                
                (each_block
                    expression: (_) @structure.each.expression
                    context: (each_block_context
                        name: (_) @structure.each.context.name
                        index: (_)? @structure.each.context.index) @structure.each.context
                    body: (_) @structure.each.body
                    else_clause: (_)? @structure.each.else) @structure.each,
                
                (await_block
                    expression: (_) @structure.await.expression
                    pending: (_)? @structure.await.pending
                    fulfilled: (_)? @structure.await.fulfilled
                    rejected: (_)? @structure.await.rejected) @structure.await
            ]
            """,
            "extract": lambda node: {
                "type": (
                    "if" if "structure.if" in node["captures"] else
                    "each" if "structure.each" in node["captures"] else
                    "await" if "structure.await" in node["captures"] else
                    "unknown"
                ),
                "expression": (
                    node["captures"].get("structure.if.expression", {}).get("text", "") or
                    node["captures"].get("structure.each.expression", {}).get("text", "") or
                    node["captures"].get("structure.await.expression", {}).get("text", "")
                )
            }
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    },
    
    "REPOSITORY_LEARNING": SVELTE_PATTERNS_FOR_LEARNING
} 