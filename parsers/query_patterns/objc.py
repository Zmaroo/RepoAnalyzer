"""Query patterns for Objective-C files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS

OBJECTIVEC_PATTERNS_FOR_LEARNING = {
    "memory_management": {
        "pattern": """
        [
            (call_expression
                function: (identifier) @mem.func.name
                (#match? @mem.func.name "^(alloc|retain|release|autorelease)$")
                arguments: (_)? @mem.func.args) @mem.func.call,
                
            (objc_message_expr
                receiver: (_) @mem.msg.receiver
                selector: (selector) @mem.msg.selector
                (#match? @mem.msg.selector "alloc|retain|release|autorelease|dealloc")) @mem.msg,
                
            (property_declaration
                attributes: (property_attributes) @mem.prop.attrs) @mem.prop
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "memory_management",
            "is_alloc_call": "mem.func.call" in node["captures"] and node["captures"].get("mem.func.name", {}).get("text", "") == "alloc",
            "is_release_call": "mem.func.call" in node["captures"] and node["captures"].get("mem.func.name", {}).get("text", "") == "release", 
            "is_memory_message": "mem.msg" in node["captures"],
            "uses_arc_attributes": "mem.prop" in node["captures"] and "strong" in (node["captures"].get("mem.prop.attrs", {}).get("text", "") or ""),
            "memory_selector": node["captures"].get("mem.msg.selector", {}).get("text", ""),
            "management_style": (
                "manual_reference_counting" if (
                    "mem.msg" in node["captures"] and
                    any(x in node["captures"].get("mem.msg.selector", {}).get("text", "") 
                        for x in ["retain", "release", "autorelease"])
                ) else
                "arc" if (
                    "mem.prop" in node["captures"] and 
                    any(x in (node["captures"].get("mem.prop.attrs", {}).get("text", "") or "")
                        for x in ["strong", "weak", "copy"])
                ) else
                "unknown"
            )
        }
    },
    
    "message_passing": {
        "pattern": """
        [
            (objc_message_expr
                receiver: (_) @msg.receiver
                selector: (selector) @msg.selector
                arguments: (_)* @msg.args) @msg.expr,
                
            (objc_selector_expr
                selector: (selector) @sel.name) @sel.expr
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "message_passing",
            "is_message_expression": "msg.expr" in node["captures"],
            "is_selector_expression": "sel.expr" in node["captures"],
            "selector_name": (
                node["captures"].get("msg.selector", {}).get("text", "") or
                node["captures"].get("sel.name", {}).get("text", "")
            ),
            "argument_count": (
                len((node["captures"].get("msg.args", {}).get("text", "") or "").split(",")) 
                if "msg.args" in node["captures"] else 0
            ),
            "uses_self_receiver": "self" in (node["captures"].get("msg.receiver", {}).get("text", "") or ""),
            "uses_super_receiver": "super" in (node["captures"].get("msg.receiver", {}).get("text", "") or "")
        }
    },
    
    "category_patterns": {
        "pattern": """
        [
            (category_interface
                name: (identifier) @cat.class
                category: (identifier) @cat.name) @cat.interface,
                
            (category_implementation
                name: (identifier) @cat.impl.class
                category: (identifier) @cat.impl.name) @cat.implementation
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "category",
            "is_category_interface": "cat.interface" in node["captures"],
            "is_category_implementation": "cat.implementation" in node["captures"],
            "extended_class": (
                node["captures"].get("cat.class", {}).get("text", "") or
                node["captures"].get("cat.impl.class", {}).get("text", "")
            ),
            "category_name": (
                node["captures"].get("cat.name", {}).get("text", "") or
                node["captures"].get("cat.impl.name", {}).get("text", "")
            ),
            "is_anonymous_category": (
                not node["captures"].get("cat.name", {}).get("text", "") or
                not node["captures"].get("cat.impl.name", {}).get("text", "")
            )
        }
    },
    
    "ui_patterns": {
        "pattern": """
        [
            (objc_message_expr
                receiver: (_) @ui.msg.receiver
                selector: (selector) @ui.msg.selector
                (#match? @ui.msg.selector "init.*WithFrame|addSubview|setDelegate|setDataSource")) @ui.msg,
                
            (class_interface
                name: (identifier) @ui.class.name
                (#match? @ui.class.name ".*View$|.*ViewController$|.*Cell$")
                superclass: (superclass_reference) @ui.class.super) @ui.class
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "ui_patterns",
            "is_ui_method_call": "ui.msg" in node["captures"],
            "is_ui_class": "ui.class" in node["captures"],
            "class_name": node["captures"].get("ui.class.name", {}).get("text", ""),
            "superclass_name": node["captures"].get("ui.class.super", {}).get("text", ""),
            "ui_selector": node["captures"].get("ui.msg.selector", {}).get("text", ""),
            "ui_component_type": (
                "view" if (
                    "ui.class" in node["captures"] and
                    "View" in node["captures"].get("ui.class.name", {}).get("text", "")
                ) else
                "view_controller" if (
                    "ui.class" in node["captures"] and
                    "ViewController" in node["captures"].get("ui.class.name", {}).get("text", "")
                ) else
                "cell" if (
                    "ui.class" in node["captures"] and
                    "Cell" in node["captures"].get("ui.class.name", {}).get("text", "")
                ) else
                "unknown"
            )
        }
    }
}

OBJECTIVEC_PATTERNS = {
    **COMMON_PATTERNS,
    
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    declarator: (function_declarator
                        declarator: (identifier) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params)
                    body: (compound_statement) @syntax.function.body) @syntax.function.def,
                (method_definition
                    selector: (selector) @syntax.method.name
                    parameters: (parameter_list)? @syntax.method.params
                    body: (compound_statement) @syntax.method.body) @syntax.method.def
            ]
            """
        },
        "class": {
            "pattern": """
            [
                (class_interface
                    name: (identifier) @syntax.class.name
                    superclass: (superclass_reference)? @syntax.class.super
                    protocols: (protocol_reference_list)? @syntax.class.protocols
                    properties: (property_declaration)* @syntax.class.properties
                    methods: (method_declaration)* @syntax.class.methods) @syntax.class.interface,
                (class_implementation
                    name: (identifier) @syntax.class.impl.name
                    superclass: (superclass_reference)? @syntax.class.impl.super
                    ivars: (instance_variables)? @syntax.class.impl.ivars) @syntax.class.implementation
            ]
            """
        },
        "protocol": {
            "pattern": """
            (protocol_declaration
                name: (identifier) @syntax.protocol.name
                protocols: (protocol_reference_list)? @syntax.protocol.protocols
                methods: (method_declaration)* @syntax.protocol.methods) @syntax.protocol.def
            """
        }
    },

    "semantics": {
        "variable": {
            "pattern": """
            [
                (declaration
                    type: (_) @semantics.variable.type
                    declarator: (identifier) @semantics.variable.name) @semantics.variable.def,
                (property_declaration
                    attributes: (property_attributes)? @semantics.property.attrs
                    type: (_) @semantics.property.type
                    name: (identifier) @semantics.property.name) @semantics.property.def
            ]
            """
        },
        "type": {
            "pattern": """
            [
                (type_identifier) @semantics.type.name,
                (protocol_qualifier) @semantics.type.protocol,
                (type_qualifier) @semantics.type.qualifier
            ]
            """
        }
    },

    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (documentation_comment) @documentation.doc
            ]
            """
        }
    },

    "structure": {
        "import": {
            "pattern": """
            [
                (preproc_include
                    path: (system_lib_string) @structure.import.system.path) @structure.import.system,
                (preproc_include
                    path: (string_literal) @structure.import.local.path) @structure.import.local,
                (import_declaration
                    path: (_) @structure.import.framework.path) @structure.import.framework
            ]
            """
        },
        "category": {
            "pattern": """
            [
                (category_interface
                    name: (identifier) @structure.category.class
                    category: (identifier) @structure.category.name) @structure.category.interface,
                (category_implementation
                    name: (identifier) @structure.category.impl.class
                    category: (identifier) @structure.category.impl.name) @structure.category.implementation
            ]
            """
        }
    },
    
    "REPOSITORY_LEARNING": OBJECTIVEC_PATTERNS_FOR_LEARNING
} 