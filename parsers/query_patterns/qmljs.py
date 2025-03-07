"""Query patterns for QML/JS files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

QMLJS_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": QueryPattern(
                pattern="""
                [
                    (object_definition
                        type: (identifier) @syntax.component.type
                        members: (object_members) @syntax.component.members) @syntax.component,
                    (property_assignment
                        name: (identifier) @syntax.property.name
                        value: (_) @syntax.property.value) @syntax.property,
                    (property_binding
                        name: (identifier) @syntax.binding.name
                        expression: (expression) @syntax.binding.expression) @syntax.binding
                ]
                """,
                extract=lambda node: {
                    "type": (
                        "component" if "syntax.component" in node["captures"] else
                        "property" if "syntax.property" in node["captures"] else
                        "binding" if "syntax.binding" in node["captures"] else
                        "other"
                    ),
                    "name": (
                        node["captures"].get("syntax.component.type", {}).get("text", "") or
                        node["captures"].get("syntax.property.name", {}).get("text", "") or
                        node["captures"].get("syntax.binding.name", {}).get("text", "")
                    )
                }
            ),
            "function": QueryPattern(
                pattern="""
                [
                    (method_definition
                        name: (identifier) @syntax.function.name
                        parameters: (formal_parameter_list) @syntax.function.params
                        body: (statement_block) @syntax.function.body) @syntax.function,
                    (signal_definition
                        name: (identifier) @syntax.signal.name
                        parameters: (formal_parameter_list)? @syntax.signal.params) @syntax.signal,
                    (property_definition
                        name: (identifier) @syntax.property.def.name
                        type: (identifier) @syntax.property.def.type) @syntax.property.def
                ]
                """,
                extract=lambda node: {
                    "type": (
                        "function" if "syntax.function" in node["captures"] else
                        "signal" if "syntax.signal" in node["captures"] else
                        "property" if "syntax.property.def" in node["captures"] else
                        "other"
                    ),
                    "name": (
                        node["captures"].get("syntax.function.name", {}).get("text", "") or
                        node["captures"].get("syntax.signal.name", {}).get("text", "") or
                        node["captures"].get("syntax.property.def.name", {}).get("text", "")
                    ),
                    "has_params": any(
                        key in node["captures"] for key in 
                        ["syntax.function.params", "syntax.signal.params"]
                    )
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "type": "comment"
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.UI_COMPONENTS: {
            "ui_component_patterns": QueryPattern(
                pattern="""
                [
                    (object_definition
                        type: (identifier) @learning.ui.comp.type
                        members: (object_members
                            (property_assignment
                                name: (identifier) @learning.ui.comp.prop.name
                                value: (_) @learning.ui.comp.prop.value))) @learning.ui.comp,
                    (object_definition
                        type: (identifier) @learning.ui.layout.type {
                            match: "^(Row|Column|Grid|Flow)Layout$" 
                        }
                        members: (object_members
                            (property_assignment)* @learning.ui.layout.props)) @learning.ui.layout,
                    (object_definition
                        type: (identifier) @learning.ui.anim.type {
                            match: "^\\w*Animation$"
                        }
                        members: (object_members
                            (property_assignment
                                name: (identifier) @learning.ui.anim.prop.name
                                value: (_) @learning.ui.anim.prop.value))) @learning.ui.anim,
                    (object_definition
                        type: (identifier) @learning.ui.states.type {
                            match: "^(State|Transition)$"
                        }
                        members: (object_members
                            (property_assignment
                                name: (identifier) @learning.ui.states.prop.name
                                value: (_) @learning.ui.states.prop.value))) @learning.ui.states
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "ui_component_patterns",
                    "is_component": "learning.ui.comp" in node["captures"],
                    "is_layout": "learning.ui.layout" in node["captures"],
                    "is_animation": "learning.ui.anim" in node["captures"],
                    "is_state_transition": "learning.ui.states" in node["captures"],
                    "component_type": node["captures"].get("learning.ui.comp.type", {}).get("text", "") or node["captures"].get("learning.ui.layout.type", {}).get("text", "") or node["captures"].get("learning.ui.anim.type", {}).get("text", "") or node["captures"].get("learning.ui.states.type", {}).get("text", ""),
                    "property_name": node["captures"].get("learning.ui.comp.prop.name", {}).get("text", "") or node["captures"].get("learning.ui.anim.prop.name", {}).get("text", "") or node["captures"].get("learning.ui.states.prop.name", {}).get("text", ""),
                    "property_value": node["captures"].get("learning.ui.comp.prop.value", {}).get("text", "") or node["captures"].get("learning.ui.anim.prop.value", {}).get("text", "") or node["captures"].get("learning.ui.states.prop.value", {}).get("text", ""),
                    "ui_element_type": (
                        "basic_component" if "learning.ui.comp" in node["captures"] else
                        "layout" if "learning.ui.layout" in node["captures"] else
                        "animation" if "learning.ui.anim" in node["captures"] else
                        "state_transition" if "learning.ui.states" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.PROPERTY_BINDING: {
            "property_binding": QueryPattern(
                pattern="""
                [
                    (property_assignment
                        name: (identifier) @learning.prop.bind.name
                        value: (binding
                            expression: (expression) @learning.prop.bind.expr)) @learning.prop.bind,
                    (property_binding
                        name: (identifier) @learning.prop.on.name
                        expression: (expression) @learning.prop.on.expr) @learning.prop.on,
                    (property_definition
                        name: (identifier) @learning.prop.def.name
                        type: (identifier) @learning.prop.def.type
                        expression: (expression)? @learning.prop.def.expr) @learning.prop.def,
                    (property_assignment
                        name: (identifier) @learning.prop.alias.name {
                            match: "^alias$"
                        }
                        value: (_) @learning.prop.alias.target) @learning.prop.alias.def
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "property_binding",
                    "is_binding": "learning.prop.bind" in node["captures"],
                    "is_on_binding": "learning.prop.on" in node["captures"],
                    "is_property_definition": "learning.prop.def" in node["captures"],
                    "is_alias": "learning.prop.alias.def" in node["captures"],
                    "property_name": node["captures"].get("learning.prop.bind.name", {}).get("text", "") or node["captures"].get("learning.prop.on.name", {}).get("text", "") or node["captures"].get("learning.prop.def.name", {}).get("text", ""),
                    "property_type": node["captures"].get("learning.prop.def.type", {}).get("text", ""),
                    "binding_expression": node["captures"].get("learning.prop.bind.expr", {}).get("text", "") or node["captures"].get("learning.prop.on.expr", {}).get("text", "") or node["captures"].get("learning.prop.def.expr", {}).get("text", ""),
                    "alias_target": node["captures"].get("learning.prop.alias.target", {}).get("text", ""),
                    "binding_type": (
                        "regular_binding" if "learning.prop.bind" in node["captures"] else
                        "on_binding" if "learning.prop.on" in node["captures"] else
                        "property_definition" if "learning.prop.def" in node["captures"] else
                        "alias" if "learning.prop.alias.def" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.SIGNALS_SLOTS: {
            "signals_slots": QueryPattern(
                pattern="""
                [
                    (signal_definition
                        name: (identifier) @learning.signal.def.name
                        parameters: (formal_parameter_list)? @learning.signal.def.params) @learning.signal.def,
                    (method_definition
                        name: (identifier) @learning.slot.name
                        parameters: (formal_parameter_list) @learning.slot.params
                        body: (statement_block) @learning.slot.body) @learning.slot.def,
                    (property_assignment
                        name: (identifier) @learning.signal.connect.name {
                            match: "^on[A-Z].*$"
                        }
                        value: (function_expression) @learning.signal.connect.handler) @learning.signal.connect,
                    (statement
                        (call_expression
                            function: (member_expression
                                object: (_) @learning.signal.emit.obj
                                property: (property_identifier) @learning.signal.emit.name)
                            arguments: (arguments) @learning.signal.emit.args)) @learning.signal.emit
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "signals_slots",
                    "is_signal_definition": "learning.signal.def" in node["captures"],
                    "is_slot_definition": "learning.slot.def" in node["captures"],
                    "is_signal_connection": "learning.signal.connect" in node["captures"],
                    "is_signal_emission": "learning.signal.emit" in node["captures"],
                    "signal_name": node["captures"].get("learning.signal.def.name", {}).get("text", "") or node["captures"].get("learning.signal.connect.name", {}).get("text", "") or node["captures"].get("learning.signal.emit.name", {}).get("text", ""),
                    "slot_name": node["captures"].get("learning.slot.name", {}).get("text", ""),
                    "signal_parameters": node["captures"].get("learning.signal.def.params", {}).get("text", ""),
                    "slot_parameters": node["captures"].get("learning.slot.params", {}).get("text", ""),
                    "signal_handler": node["captures"].get("learning.signal.connect.handler", {}).get("text", ""),
                    "signal_component": (
                        "definition" if "learning.signal.def" in node["captures"] else
                        "connection" if "learning.signal.connect" in node["captures"] else
                        "emission" if "learning.signal.emit" in node["captures"] else
                        "slot" if "learning.slot.def" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.QML_JS_INTEGRATION: {
            "qml_js_integration": QueryPattern(
                pattern="""
                [
                    (method_definition
                        name: (identifier) @learning.js.func.name
                        parameters: (formal_parameter_list) @learning.js.func.params
                        body: (statement_block) @learning.js.func.body) @learning.js.func,
                    (statement
                        (call_expression
                            function: (identifier) @learning.js.qt.func.name {
                                match: "^(Qt\\.createComponent|Qt\\.createQmlObject|Component\\.createObject)$"
                            }
                            arguments: (arguments) @learning.js.qt.func.args)) @learning.js.qt.func,
                    (property_assignment
                        value: (array
                            (expression)* @learning.js.model.items)) @learning.js.model,
                    (import_statement
                        (string) @learning.js.import.path) @learning.js.import,
                    (statement
                        (call_expression
                            function: (member_expression
                                object: (identifier) @learning.js.console.obj {
                                    match: "^console$"
                                }
                                property: (property_identifier) @learning.js.console.method {
                                    match: "^(log|debug|info|warn|error)$"
                                }))) @learning.js.console.log
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "qml_js_integration",
                    "is_js_function": "learning.js.func" in node["captures"],
                    "uses_qt_js_apis": "learning.js.qt.func" in node["captures"],
                    "uses_js_model": "learning.js.model" in node["captures"],
                    "uses_js_import": "learning.js.import" in node["captures"],
                    "uses_console_logging": "learning.js.console.log" in node["captures"],
                    "function_name": node["captures"].get("learning.js.func.name", {}).get("text", ""),
                    "qt_function": node["captures"].get("learning.js.qt.func.name", {}).get("text", ""),
                    "import_path": node["captures"].get("learning.js.import.path", {}).get("text", ""),
                    "console_method": node["captures"].get("learning.js.console.method", {}).get("text", ""),
                    "js_pattern_type": (
                        "function_definition" if "learning.js.func" in node["captures"] else
                        "qt_api_usage" if "learning.js.qt.func" in node["captures"] else
                        "model_data" if "learning.js.model" in node["captures"] else
                        "import" if "learning.js.import" in node["captures"] else
                        "console_logging" if "learning.js.console.log" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    }
}

QMLJS_PATTERNS_FOR_LEARNING = {
    "ui_component_patterns": {
        "pattern": """
        [
            (object_definition
                type: (identifier) @ui.comp.type
                members: (object_members
                    (property_assignment
                        name: (identifier) @ui.comp.prop.name
                        value: (_) @ui.comp.prop.value))) @ui.comp,
                        
            (object_definition
                type: (identifier) @ui.layout.type {
                    match: "^(Row|Column|Grid|Flow)Layout$" 
                }
                members: (object_members
                    (property_assignment)* @ui.layout.props)) @ui.layout,
                    
            (object_definition
                type: (identifier) @ui.anim.type {
                    match: "^\\w*Animation$"
                }
                members: (object_members
                    (property_assignment
                        name: (identifier) @ui.anim.prop.name
                        value: (_) @ui.anim.prop.value))) @ui.anim,
                        
            (object_definition
                type: (identifier) @ui.states.type {
                    match: "^(State|Transition)$"
                }
                members: (object_members
                    (property_assignment
                        name: (identifier) @ui.states.prop.name
                        value: (_) @ui.states.prop.value))) @ui.states
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "ui_component_patterns",
            "is_component": "ui.comp" in node["captures"],
            "is_layout": "ui.layout" in node["captures"],
            "is_animation": "ui.anim" in node["captures"],
            "is_state_transition": "ui.states" in node["captures"],
            "component_type": node["captures"].get("ui.comp.type", {}).get("text", "") or node["captures"].get("ui.layout.type", {}).get("text", "") or node["captures"].get("ui.anim.type", {}).get("text", "") or node["captures"].get("ui.states.type", {}).get("text", ""),
            "property_name": node["captures"].get("ui.comp.prop.name", {}).get("text", "") or node["captures"].get("ui.anim.prop.name", {}).get("text", "") or node["captures"].get("ui.states.prop.name", {}).get("text", ""),
            "property_value": node["captures"].get("ui.comp.prop.value", {}).get("text", "") or node["captures"].get("ui.anim.prop.value", {}).get("text", "") or node["captures"].get("ui.states.prop.value", {}).get("text", ""),
            "ui_element_type": (
                "basic_component" if "ui.comp" in node["captures"] else
                "layout" if "ui.layout" in node["captures"] else
                "animation" if "ui.anim" in node["captures"] else
                "state_transition" if "ui.states" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "property_binding": {
        "pattern": """
        [
            (property_assignment
                name: (identifier) @prop.bind.name
                value: (binding
                    expression: (expression) @prop.bind.expr)) @prop.bind,
                    
            (property_binding
                name: (identifier) @prop.on.name
                expression: (expression) @prop.on.expr) @prop.on,
                
            (property_definition
                name: (identifier) @prop.def.name
                type: (identifier) @prop.def.type
                expression: (expression)? @prop.def.expr) @prop.def,
                
            (property_assignment
                name: (identifier) @prop.alias.name {
                    match: "^alias$"
                }
                value: (_) @prop.alias.target) @prop.alias.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "property_binding",
            "is_binding": "prop.bind" in node["captures"],
            "is_on_binding": "prop.on" in node["captures"],
            "is_property_definition": "prop.def" in node["captures"],
            "is_alias": "prop.alias.def" in node["captures"],
            "property_name": node["captures"].get("prop.bind.name", {}).get("text", "") or node["captures"].get("prop.on.name", {}).get("text", "") or node["captures"].get("prop.def.name", {}).get("text", ""),
            "property_type": node["captures"].get("prop.def.type", {}).get("text", ""),
            "binding_expression": node["captures"].get("prop.bind.expr", {}).get("text", "") or node["captures"].get("prop.on.expr", {}).get("text", "") or node["captures"].get("prop.def.expr", {}).get("text", ""),
            "alias_target": node["captures"].get("prop.alias.target", {}).get("text", ""),
            "binding_type": (
                "regular_binding" if "prop.bind" in node["captures"] else
                "on_binding" if "prop.on" in node["captures"] else
                "property_definition" if "prop.def" in node["captures"] else
                "alias" if "prop.alias.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "signals_slots": {
        "pattern": """
        [
            (signal_definition
                name: (identifier) @signal.def.name
                parameters: (formal_parameter_list)? @signal.def.params) @signal.def,
                
            (method_definition
                name: (identifier) @slot.name
                parameters: (formal_parameter_list) @slot.params
                body: (statement_block) @slot.body) @slot.def,
                
            (property_assignment
                name: (identifier) @signal.connect.name {
                    match: "^on[A-Z].*$"
                }
                value: (function_expression) @signal.connect.handler) @signal.connect,
                
            (statement
                (call_expression
                    function: (member_expression
                        object: (_) @signal.emit.obj
                        property: (property_identifier) @signal.emit.name)
                    arguments: (arguments) @signal.emit.args)) @signal.emit
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "signals_slots",
            "is_signal_definition": "signal.def" in node["captures"],
            "is_slot_definition": "slot.def" in node["captures"],
            "is_signal_connection": "signal.connect" in node["captures"],
            "is_signal_emission": "signal.emit" in node["captures"],
            "signal_name": node["captures"].get("signal.def.name", {}).get("text", "") or node["captures"].get("signal.connect.name", {}).get("text", "") or node["captures"].get("signal.emit.name", {}).get("text", ""),
            "slot_name": node["captures"].get("slot.name", {}).get("text", ""),
            "signal_parameters": node["captures"].get("signal.def.params", {}).get("text", ""),
            "slot_parameters": node["captures"].get("slot.params", {}).get("text", ""),
            "signal_handler": node["captures"].get("signal.connect.handler", {}).get("text", ""),
            "signal_component": (
                "definition" if "signal.def" in node["captures"] else
                "connection" if "signal.connect" in node["captures"] else
                "emission" if "signal.emit" in node["captures"] else
                "slot" if "slot.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "qml_js_integration": {
        "pattern": """
        [
            (method_definition
                name: (identifier) @js.func.name
                parameters: (formal_parameter_list) @js.func.params
                body: (statement_block) @js.func.body) @js.func,
                
            (statement
                (call_expression
                    function: (identifier) @js.qt.func.name {
                        match: "^(Qt\\.createComponent|Qt\\.createQmlObject|Component\\.createObject)$"
                    }
                    arguments: (arguments) @js.qt.func.args)) @js.qt.func,
                    
            (property_assignment
                value: (array
                    (expression)* @js.model.items)) @js.model,
                    
            (import_statement
                (string) @js.import.path) @js.import,
                
            (statement
                (call_expression
                    function: (member_expression
                        object: (identifier) @js.console.obj {
                            match: "^console$"
                        }
                        property: (property_identifier) @js.console.method {
                            match: "^(log|debug|info|warn|error)$"
                        }))) @js.console.log
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "qml_js_integration",
            "is_js_function": "js.func" in node["captures"],
            "uses_qt_js_apis": "js.qt.func" in node["captures"],
            "uses_js_model": "js.model" in node["captures"],
            "uses_js_import": "js.import" in node["captures"],
            "uses_console_logging": "js.console.log" in node["captures"],
            "function_name": node["captures"].get("js.func.name", {}).get("text", ""),
            "qt_function": node["captures"].get("js.qt.func.name", {}).get("text", ""),
            "import_path": node["captures"].get("js.import.path", {}).get("text", ""),
            "console_method": node["captures"].get("js.console.method", {}).get("text", ""),
            "js_pattern_type": (
                "function_definition" if "js.func" in node["captures"] else
                "qt_api_usage" if "js.qt.func" in node["captures"] else
                "model_data" if "js.model" in node["captures"] else
                "import" if "js.import" in node["captures"] else
                "console_logging" if "js.console.log" in node["captures"] else
                "unknown"
            )
        }
    }
}

QMLJS_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "component": {
            "pattern": """
            [
                (object_definition
                    type: (identifier) @syntax.component.type
                    members: (object_members) @syntax.component.members) @syntax.component,
                
                (property_assignment
                    name: (identifier) @syntax.property.name
                    value: (_) @syntax.property.value) @syntax.property,
                
                (property_binding
                    name: (identifier) @syntax.binding.name
                    expression: (expression) @syntax.binding.expression) @syntax.binding
            ]
            """
        },
        "function": {
            "pattern": """
            [
                (method_definition
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameter_list) @syntax.function.params
                    body: (statement_block) @syntax.function.body) @syntax.function,
                
                (signal_definition
                    name: (identifier) @syntax.signal.name
                    parameters: (formal_parameter_list)? @syntax.signal.params) @syntax.signal,
                
                (property_definition
                    name: (identifier) @syntax.property.def.name
                    type: (identifier) @syntax.property.def.type) @syntax.property.def
            ]
            """
        }
    },
    
    "structure": {
        "import": {
            "pattern": """
            [
                (import_statement
                    (string) @structure.import.path) @structure.import,
                
                (pragma_statement
                    (identifier) @structure.pragma.name
                    (string) @structure.pragma.value) @structure.pragma
            ]
            """
        },
        "expression": {
            "pattern": """
            [
                (binding
                    expression: (expression) @structure.binding.expression) @structure.binding,
                
                (function_expression
                    parameters: (formal_parameter_list) @structure.function.params
                    body: (statement_block) @structure.function.body) @structure.function,
                
                (call_expression
                    function: (_) @structure.call.function
                    arguments: (arguments) @structure.call.args) @structure.call
            ]
            """
        }
    },
    
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": QMLJS_PATTERNS_FOR_LEARNING
} 