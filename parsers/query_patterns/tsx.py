"""TSX-specific Tree-sitter patterns."""

from parsers.types import FileType
from .js_ts_shared import JS_TS_SHARED_PATTERNS
from .typescript import TYPESCRIPT_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

TSX_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "component_patterns": QueryPattern(
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @component.func.name
                        parameters: (formal_parameters) @component.func.params
                        return_type: (type_annotation)? @component.func.return
                        body: (statement_block
                            (return_statement
                                (jsx_element) @component.func.jsx)) @component.func.body) @component.func.comp,
                        
                    (variable_declaration
                        (variable_declarator
                            name: (identifier) @component.var.name
                            value: (arrow_function
                                parameters: (formal_parameters) @component.var.params
                                return_type: (type_annotation)? @component.var.return
                                body: [(jsx_element) (statement_block)])) @component.var.decl) @component.var.comp,
                        
                    (class_declaration
                        name: (identifier) @component.class.name
                        body: (class_body
                            (method_definition
                                name: (property_identifier) @component.class.render {
                                    match: "^render$"
                                }
                                body: (statement_block
                                    (return_statement
                                        (jsx_element) @component.class.jsx)) @component.class.render_body)) @component.class.body) @component.class.comp
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "component_patterns",
                    "is_function_component": "component.func.comp" in node["captures"],
                    "is_arrow_component": "component.var.comp" in node["captures"],
                    "is_class_component": "component.class.comp" in node["captures"],
                    "component_name": (
                        node["captures"].get("component.func.name", {}).get("text", "") or 
                        node["captures"].get("component.var.name", {}).get("text", "") or 
                        node["captures"].get("component.class.name", {}).get("text", "")
                    ),
                    "has_type_annotation": (
                        ("component.func.return" in node["captures"] and node["captures"].get("component.func.return", {}).get("text", "") != "") or
                        ("component.var.return" in node["captures"] and node["captures"].get("component.var.return", {}).get("text", "") != "")
                    ),
                    "component_type": (
                        "function_component" if "component.func.comp" in node["captures"] else
                        "arrow_function_component" if "component.var.comp" in node["captures"] else 
                        "class_component" if "component.class.comp" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches React component patterns",
                examples=[
                    "function MyComponent(props: Props) { return <div />; }",
                    "const MyComponent = () => <div />;",
                    "class MyComponent extends React.Component { render() { return <div />; } }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "hooks_usage": QueryPattern(
                pattern="""
                [
                    (call_expression
                        function: (identifier) @hook.call.name {
                            match: "^use[A-Z].*$"
                        }
                        arguments: (arguments) @hook.call.args) @hook.call,
                        
                    (lexical_declaration
                        declarator: (variable_declarator
                            name: [(identifier) @hook.state.var
                                  (array_pattern
                                    (identifier) @hook.state.var 
                                    (identifier) @hook.state.setter)]
                            value: (call_expression
                                function: (identifier) @hook.state.func {
                                    match: "^(useState|useReducer)$"
                                }
                                arguments: (arguments) @hook.state.args)) @hook.state.decl) @hook.state,
                        
                    (call_expression
                        function: (identifier) @hook.effect.name {
                            match: "^(useEffect|useLayoutEffect)$"
                        }
                        arguments: (arguments
                            (arrow_function) @hook.effect.callback
                            (array_expression)? @hook.effect.deps)) @hook.effect,
                        
                    (call_expression
                        function: (identifier) @hook.context.name {
                            match: "^(useContext)$"
                        }
                        arguments: (arguments) @hook.context.args) @hook.context
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "hooks_usage",
                    "is_custom_hook": "hook.call" in node["captures"] and node["captures"].get("hook.call.name", {}).get("text", "").startswith("use"),
                    "is_state_hook": "hook.state" in node["captures"],
                    "is_effect_hook": "hook.effect" in node["captures"],
                    "is_context_hook": "hook.context" in node["captures"],
                    "hook_name": (
                        node["captures"].get("hook.call.name", {}).get("text", "") or
                        node["captures"].get("hook.state.func", {}).get("text", "") or
                        node["captures"].get("hook.effect.name", {}).get("text", "") or
                        node["captures"].get("hook.context.name", {}).get("text", "")
                    ),
                    "state_var": node["captures"].get("hook.state.var", {}).get("text", ""),
                    "has_deps_array": "hook.effect" in node["captures"] and "hook.effect.deps" in node["captures"] and node["captures"].get("hook.effect.deps", {}).get("text", "") != "",
                    "hook_type": (
                        "custom_hook" if "hook.call" in node["captures"] and node["captures"].get("hook.call.name", {}).get("text", "").startswith("use") else
                        "state_management" if "hook.state" in node["captures"] else
                        "effect" if "hook.effect" in node["captures"] else
                        "context" if "hook.context" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches React hooks usage patterns",
                examples=[
                    "const [state, setState] = useState(0);",
                    "useEffect(() => { }, [deps]);",
                    "const value = useContext(MyContext);"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "jsx_patterns": QueryPattern(
                pattern="""
                [
                    (jsx_element
                        opening_element: (jsx_opening_element
                            name: (_) @jsx.element.name
                            attributes: (jsx_attributes
                                [(jsx_attribute
                                    name: (jsx_attribute_name) @jsx.element.attr.name
                                    value: (_)? @jsx.element.attr.value)
                                 (jsx_expression
                                    (binary_expression
                                        left: (identifier) @jsx.element.cond.left
                                        right: (_) @jsx.element.cond.right) @jsx.element.attr.condition) @jsx.element.attr.expr])* @jsx.element.attrs)
                        @jsx.element.open) @jsx.element,
                        
                    (jsx_self_closing_element
                        name: (_) @jsx.self.name
                        attributes: (jsx_attributes
                            [(jsx_attribute
                                name: (jsx_attribute_name) @jsx.self.attr.name
                                value: (_)? @jsx.self.attr.value)
                             (jsx_expression) @jsx.self.attr.expr]*) @jsx.self.attrs) @jsx.self,
                             
                    (jsx_expression
                        [(conditional_expression
                            condition: (_) @jsx.cond.test
                            consequence: (_) @jsx.cond.then
                            alternative: (_) @jsx.cond.else) @jsx.conditional_render
                         (binary_expression
                            left: (_) @jsx.binary.left
                            right: (_) @jsx.binary.right) @jsx.binary
                         (call_expression
                            function: (member_expression
                                object: (_) @jsx.map.array
                                property: (property_identifier) @jsx.map.method {
                                    match: "^map$"
                                }) @jsx.map.func
                            arguments: (arguments
                                (arrow_function) @jsx.map.callback)) @jsx.array_map]) @jsx.expr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "jsx_patterns",
                    "is_jsx_element": "jsx.element" in node["captures"],
                    "is_self_closing": "jsx.self" in node["captures"],
                    "is_conditional_render": "jsx.conditional_render" in node["captures"],
                    "is_array_map": "jsx.array_map" in node["captures"],
                    "element_name": node["captures"].get("jsx.element.name", {}).get("text", "") or node["captures"].get("jsx.self.name", {}).get("text", ""),
                    "attributes": [attr.get("text", "") for attr in node["captures"].get("jsx.element.attr.name", []) + node["captures"].get("jsx.self.attr.name", [])],
                    "has_condition": "jsx.element.attr.condition" in node["captures"],
                    "map_array": node["captures"].get("jsx.map.array", {}).get("text", ""),
                    "jsx_pattern_type": (
                        "element" if "jsx.element" in node["captures"] else
                        "self_closing_element" if "jsx.self" in node["captures"] else
                        "conditional_rendering" if "jsx.conditional_render" in node["captures"] else
                        "array_mapping" if "jsx.array_map" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches JSX usage patterns",
                examples=[
                    "<div className={condition ? 'a' : 'b'} />",
                    "{items.map(item => <Item key={item.id} {...item} />)}",
                    "{condition && <Component />}"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "typescript_integration": QueryPattern(
                pattern="""
                [
                    (interface_declaration
                        name: (type_identifier) @ts.interface.name {
                            match: "^.*Props$"
                        }
                        body: (object_type) @ts.interface.body) @ts.interface,
                        
                    (type_alias_declaration
                        name: (type_identifier) @ts.type.name {
                            match: "^.*Props$"
                        }
                        value: (_) @ts.type.value) @ts.type,
                        
                    (export_statement
                        [(interface_declaration) (type_alias_declaration) (enum_declaration)] @ts.export.declaration) @ts.export,
                        
                    (arrow_function
                        parameters: (formal_parameters
                            (required_parameter
                                pattern: (identifier) @ts.param.name
                                type: (type_annotation
                                    (type_identifier) @ts.param.type)) @ts.typed_param)+ @ts.params) @ts.function,
                                    
                    (property_signature
                        name: (property_identifier) @ts.prop.name
                        type: (type_annotation) @ts.prop.type
                        value: (_)? @ts.prop.default) @ts.prop
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "typescript_integration",
                    "is_props_interface": "ts.interface" in node["captures"] and node["captures"].get("ts.interface.name", {}).get("text", "").endswith("Props"),
                    "is_props_type": "ts.type" in node["captures"] and node["captures"].get("ts.type.name", {}).get("text", "").endswith("Props"),
                    "is_export": "ts.export" in node["captures"],
                    "is_typed_function": "ts.function" in node["captures"],
                    "is_typed_property": "ts.prop" in node["captures"],
                    "name": (
                        node["captures"].get("ts.interface.name", {}).get("text", "") or
                        node["captures"].get("ts.type.name", {}).get("text", "") or
                        node["captures"].get("ts.param.name", {}).get("text", "") or
                        node["captures"].get("ts.prop.name", {}).get("text", "")
                    ),
                    "type_name": node["captures"].get("ts.param.type", {}).get("text", ""),
                    "ts_pattern_type": (
                        "props_interface" if "ts.interface" in node["captures"] and node["captures"].get("ts.interface.name", {}).get("text", "").endswith("Props") else
                        "props_type_alias" if "ts.type" in node["captures"] and node["captures"].get("ts.type.name", {}).get("text", "").endswith("Props") else
                        "type_export" if "ts.export" in node["captures"] else
                        "typed_function" if "ts.function" in node["captures"] else
                        "typed_property" if "ts.prop" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches TypeScript integration patterns in React",
                examples=[
                    "interface ComponentProps { prop: string; }",
                    "type Props = { prop: string; };",
                    "function Component(props: Props) { }"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

TSX_PATTERNS = {
    **JS_TS_SHARED_PATTERNS,  # Include shared JS/TS patterns
    **TYPESCRIPT_PATTERNS,  # Include TypeScript patterns
    
    PatternCategory.SYNTAX: {
        **JS_TS_SHARED_PATTERNS.get("syntax", {}),  # Keep shared JS/TS syntax patterns
        **TYPESCRIPT_PATTERNS.get("syntax", {}),  # Keep TypeScript syntax patterns
        PatternPurpose.UNDERSTANDING: {
            "jsx": QueryPattern(
                pattern="""
                [
                    (jsx_element
                        opening_element: (jsx_opening_element
                            name: (_) @syntax.jsx.tag.name
                            type_arguments: (type_arguments)? @syntax.jsx.type_args
                            attributes: (jsx_attributes
                                [(jsx_attribute
                                    name: (jsx_attribute_name) @syntax.jsx.attr.name
                                    value: (_)? @syntax.jsx.attr.value)
                                 (jsx_expression) @syntax.jsx.attr.expression]*)?
                        ) @syntax.jsx.open
                        children: [
                            (jsx_text) @syntax.jsx.text
                            (jsx_expression) @syntax.jsx.expression
                            (jsx_element) @syntax.jsx.child
                            (jsx_self_closing_element) @syntax.jsx.child.self_closing
                        ]* @syntax.jsx.children
                        closing_element: (jsx_closing_element)? @syntax.jsx.close
                    ) @syntax.jsx.element,
                    
                    (jsx_self_closing_element
                        name: (_) @syntax.jsx.self.name
                        type_arguments: (type_arguments)? @syntax.jsx.self.type_args
                        attributes: (jsx_attributes
                            [(jsx_attribute
                                name: (jsx_attribute_name) @syntax.jsx.self.attr.name
                                value: (_)? @syntax.jsx.self.attr.value)
                             (jsx_expression) @syntax.jsx.self.attr.expression]*)?
                    ) @syntax.jsx.self
                ]
                """,
                extract=lambda node: {
                    "tag": node["captures"].get("syntax.jsx.tag.name", {}).get("text", "") or
                           node["captures"].get("syntax.jsx.self.name", {}).get("text", ""),
                    "attributes": [
                        {
                            "name": attr.get("text", ""),
                            "value": val.get("text", "") if val else None
                        }
                        for attr, val in zip(
                            node["captures"].get("syntax.jsx.attr.name", []) +
                            node["captures"].get("syntax.jsx.self.attr.name", []),
                            node["captures"].get("syntax.jsx.attr.value", []) +
                            node["captures"].get("syntax.jsx.self.attr.value", [])
                        )
                    ]
                },
                description="Matches TSX elements and attributes",
                examples=[
                    "<Component<Props> prop={value} />",
                    "<div className='container'>...</div>"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        **JS_TS_SHARED_PATTERNS.get("semantics", {}),  # Keep shared JS/TS semantic patterns
        **TYPESCRIPT_PATTERNS.get("semantics", {}),  # Keep TypeScript semantic patterns
        PatternPurpose.UNDERSTANDING: {
            "jsx_type": QueryPattern(
                pattern="""
                [
                    (jsx_opening_element
                        type_arguments: (type_arguments
                            [(type_identifier) @semantics.jsx.type.name
                             (union_type) @semantics.jsx.type.union
                             (intersection_type) @semantics.jsx.type.intersection
                             (generic_type) @semantics.jsx.type.generic]*
                        )) @semantics.jsx.type.args,
                        
                    (jsx_self_closing_element
                        type_arguments: (type_arguments
                            [(type_identifier) @semantics.jsx.type.self.name
                             (union_type) @semantics.jsx.type.self.union
                             (intersection_type) @semantics.jsx.type.self.intersection
                             (generic_type) @semantics.jsx.type.self.generic]*
                        )) @semantics.jsx.type.self.args
                ]
                """,
                extract=lambda node: {
                    "type": node["captures"].get("semantics.jsx.type.name", {}).get("text", "") or
                           node["captures"].get("semantics.jsx.type.self.name", {}).get("text", ""),
                    "kind": ("union" if "semantics.jsx.type.union" in node["captures"] or
                                     "semantics.jsx.type.self.union" in node["captures"] else
                            "intersection" if "semantics.jsx.type.intersection" in node["captures"] or
                                           "semantics.jsx.type.self.intersection" in node["captures"] else
                            "generic" if "semantics.jsx.type.generic" in node["captures"] or
                                      "semantics.jsx.type.self.generic" in node["captures"] else
                            "basic")
                },
                description="Matches TSX type system usage",
                examples=[
                    "<Component<Props> />",
                    "<Generic<T | U> />",
                    "<Component<A & B> />"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
TSX_PATTERNS.update(TSX_PATTERNS_FOR_LEARNING)