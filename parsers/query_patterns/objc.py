"""Query patterns for Objective-C files."""

from parsers.types import FileType
from .common import COMMON_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

OBJECTIVEC_PATTERNS = {
    **COMMON_PATTERNS,
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                           node["captures"].get("syntax.method.name", {}).get("text", ""),
                    "type": "function" if "syntax.function.def" in node["captures"] else "method"
                },
                description="Matches Objective-C function and method definitions",
                examples=[
                    "void processData(int value) { }",
                    "- (void)viewDidLoad { }"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "class": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                           node["captures"].get("syntax.class.impl.name", {}).get("text", ""),
                    "type": "interface" if "syntax.class.interface" in node["captures"] else "implementation"
                },
                description="Matches Objective-C class interface and implementation",
                examples=[
                    "@interface MyClass : NSObject",
                    "@implementation MyClass"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "protocol": QueryPattern(
                pattern="""
                (protocol_declaration
                    name: (identifier) @syntax.protocol.name
                    protocols: (protocol_reference_list)? @syntax.protocol.protocols
                    methods: (method_declaration)* @syntax.protocol.methods) @syntax.protocol.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.protocol.name", {}).get("text", ""),
                    "has_protocols": bool(node["captures"].get("syntax.protocol.protocols", None))
                },
                description="Matches Objective-C protocol declarations",
                examples=[
                    "@protocol MyProtocol <NSObject>",
                    "@protocol DataSource"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable": QueryPattern(
                pattern="""
                [
                    (declaration
                        type: (_) @semantics.variable.type
                        declarator: (identifier) @semantics.variable.name) @semantics.variable.def,
                    (property_declaration
                        attributes: (property_attributes)? @semantics.property.attrs
                        type: (_) @semantics.property.type
                        name: (identifier) @semantics.property.name) @semantics.property.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.variable.name", {}).get("text", "") or
                           node["captures"].get("semantics.property.name", {}).get("text", ""),
                    "type": node["captures"].get("semantics.variable.type", {}).get("text", "") or
                           node["captures"].get("semantics.property.type", {}).get("text", "")
                },
                description="Matches Objective-C variable and property declarations",
                examples=[
                    "NSString *name;",
                    "@property (nonatomic, strong) NSArray *items;"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "type": QueryPattern(
                pattern="""
                [
                    (type_identifier) @semantics.type.name,
                    (protocol_qualifier) @semantics.type.protocol,
                    (type_qualifier) @semantics.type.qualifier
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "protocol": node["captures"].get("semantics.type.protocol", {}).get("text", ""),
                    "qualifier": node["captures"].get("semantics.type.qualifier", {}).get("text", "")
                },
                description="Matches Objective-C type declarations",
                examples=[
                    "NSString",
                    "id<NSCoding>",
                    "const NSInteger"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (documentation_comment) @documentation.doc
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                           node["captures"].get("documentation.doc", {}).get("text", "")
                },
                description="Matches Objective-C comments and documentation",
                examples=[
                    "// Single line comment",
                    "/* Block comment */",
                    "/** Documentation comment */"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import": QueryPattern(
                pattern="""
                [
                    (preproc_include
                        path: (system_lib_string) @structure.import.system.path) @structure.import.system,
                    (preproc_include
                        path: (string_literal) @structure.import.local.path) @structure.import.local,
                    (import_declaration
                        path: (_) @structure.import.framework.path) @structure.import.framework
                ]
                """,
                extract=lambda node: {
                    "path": node["captures"].get("structure.import.system.path", {}).get("text", "") or
                           node["captures"].get("structure.import.local.path", {}).get("text", "") or
                           node["captures"].get("structure.import.framework.path", {}).get("text", ""),
                    "type": ("system" if "structure.import.system" in node["captures"] else
                            "local" if "structure.import.local" in node["captures"] else
                            "framework")
                },
                description="Matches Objective-C import statements",
                examples=[
                    "#import <Foundation/Foundation.h>",
                    "#import \"MyClass.h\"",
                    "@import UIKit;"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "category": QueryPattern(
                pattern="""
                [
                    (category_interface
                        name: (identifier) @structure.category.class
                        category: (identifier) @structure.category.name) @structure.category.interface,
                    (category_implementation
                        name: (identifier) @structure.category.impl.class
                        category: (identifier) @structure.category.impl.name) @structure.category.implementation
                ]
                """,
                extract=lambda node: {
                    "class_name": node["captures"].get("structure.category.class", {}).get("text", "") or
                                 node["captures"].get("structure.category.impl.class", {}).get("text", ""),
                    "category_name": node["captures"].get("structure.category.name", {}).get("text", "") or
                                   node["captures"].get("structure.category.impl.name", {}).get("text", ""),
                    "type": "interface" if "structure.category.interface" in node["captures"] else "implementation"
                },
                description="Matches Objective-C category declarations",
                examples=[
                    "@interface NSString (MyAdditions)",
                    "@implementation NSArray (Utilities)"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for Objective-C
OBJECTIVEC_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "memory_management": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
                },
                description="Matches Objective-C memory management patterns",
                examples=[
                    "[object retain]",
                    "@property (nonatomic, strong) NSString *name;",
                    "[[NSObject alloc] init]"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "message_passing": QueryPattern(
                pattern="""
                [
                    (objc_message_expr
                        receiver: (_) @msg.receiver
                        selector: (selector) @msg.selector
                        arguments: (_)* @msg.args) @msg.expr,
                        
                    (objc_selector_expr
                        selector: (selector) @sel.name) @sel.expr
                ]
                """,
                extract=lambda node: {
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
                },
                description="Matches Objective-C message passing patterns",
                examples=[
                    "[self doSomething]",
                    "[object methodWithArg:value]",
                    "@selector(method:)"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "category_patterns": QueryPattern(
                pattern="""
                [
                    (category_interface
                        name: (identifier) @cat.class
                        category: (identifier) @cat.name) @cat.interface,
                        
                    (category_implementation
                        name: (identifier) @cat.impl.class
                        category: (identifier) @cat.impl.name) @cat.implementation
                ]
                """,
                extract=lambda node: {
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
                },
                description="Matches Objective-C category patterns",
                examples=[
                    "@interface NSString (MyAdditions)",
                    "@implementation UIView (Animations)"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "ui_patterns": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
                },
                description="Matches Objective-C UI patterns",
                examples=[
                    "@interface MyViewController : UIViewController",
                    "[view addSubview:subview]",
                    "[[UIView alloc] initWithFrame:frame]"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
OBJECTIVEC_PATTERNS.update(OBJECTIVEC_PATTERNS_FOR_LEARNING) 