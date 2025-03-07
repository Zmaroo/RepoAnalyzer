"""Query patterns for Vue files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

VUE_PATTERNS_FOR_LEARNING = {
    "component_structure": {
        "pattern": """
        [
            (component
                (template_element
                    (start_tag) @comp.template.start
                    (_)* @comp.template.content
                    (end_tag) @comp.template.end) @comp.template
                (script_element
                    (start_tag) @comp.script.start
                    (raw_text) @comp.script.content
                    (end_tag) @comp.script.end) @comp.script
                (style_element
                    (start_tag) @comp.style.start
                    (_)? @comp.style.content
                    (end_tag) @comp.style.end)? @comp.style) @comp.sfc,
                
            (element
                (start_tag
                    name: (_) @comp.element.name
                    attributes: (attribute
                        name: (attribute_name) @comp.element.attr.name
                        value: (attribute_value) @comp.element.attr.value)* @comp.element.attrs) @comp.element.start
                (_)* @comp.element.children
                (end_tag) @comp.element.end) @comp.element
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "component_structure",
            "is_single_file_component": "comp.sfc" in node["captures"],
            "is_element": "comp.element" in node["captures"] and "comp.sfc" not in node["captures"],
            "has_template": "comp.template" in node["captures"],
            "has_script": "comp.script" in node["captures"],
            "has_style": "comp.style" in node["captures"] and node["captures"].get("comp.style.content", {}).get("text", "") != "",
            "element_name": node["captures"].get("comp.element.name", {}).get("text", ""),
            "element_attributes": [attr.get("text", "") for attr in node["captures"].get("comp.element.attr.name", [])],
            "component_type": (
                "single_file_component" if "comp.sfc" in node["captures"] else
                "element" if "comp.element" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "template_directives": {
        "pattern": """
        [
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-if$"
                }
                value: (attribute_value) @dir.if.value) @dir.if,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-else-if$"
                }
                value: (attribute_value) @dir.else_if.value) @dir.else_if,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-else$"
                }) @dir.else,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-for$"
                }
                value: (attribute_value) @dir.for.value) @dir.for,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-model$"
                }
                value: (attribute_value) @dir.model.value) @dir.model,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-bind$|^:"
                }
                value: (attribute_value) @dir.bind.value) @dir.bind,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-on$|^@"
                }
                value: (attribute_value) @dir.on.value) @dir.on,
                
            (directive_attribute
                name: (directive_name) @dir.name {
                    match: "^v-slot$|^#"
                }
                value: (attribute_value) @dir.slot.value) @dir.slot
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "template_directives",
            "is_conditional": any(key in node["captures"] for key in ["dir.if", "dir.else_if", "dir.else"]),
            "is_loop": "dir.for" in node["captures"],
            "is_binding": "dir.bind" in node["captures"] or "dir.model" in node["captures"],
            "is_event": "dir.on" in node["captures"],
            "is_slot": "dir.slot" in node["captures"],
            "directive_name": node["captures"].get("dir.name", {}).get("text", ""),
            "directive_value": (
                node["captures"].get("dir.if.value", {}).get("text", "") or
                node["captures"].get("dir.else_if.value", {}).get("text", "") or
                node["captures"].get("dir.for.value", {}).get("text", "") or
                node["captures"].get("dir.model.value", {}).get("text", "") or
                node["captures"].get("dir.bind.value", {}).get("text", "") or
                node["captures"].get("dir.on.value", {}).get("text", "") or
                node["captures"].get("dir.slot.value", {}).get("text", "")
            ),
            "directive_type": (
                "v-if" if "dir.if" in node["captures"] else
                "v-else-if" if "dir.else_if" in node["captures"] else
                "v-else" if "dir.else" in node["captures"] else
                "v-for" if "dir.for" in node["captures"] else
                "v-model" if "dir.model" in node["captures"] else
                "v-bind" if "dir.bind" in node["captures"] else
                "v-on" if "dir.on" in node["captures"] else
                "v-slot" if "dir.slot" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "script_patterns": {
        "pattern": """
        [
            (script_element
                (start_tag
                    attributes: [(attribute
                        name: (attribute_name) @script.attr.name {
                            match: "^lang$"
                        }
                        value: (attribute_value) @script.attr.lang)
                    (attribute
                        name: (attribute_name) @script.attr.name {
                            match: "^setup$"
                        })]) @script.start
                (raw_text) @script.content
                (end_tag)) @script.setup,
                
            (raw_text) @script.options.api {
                match: "\\bexport\\s+default\\s+\\{[^}]+\\}"
            },
            
            (raw_text) @script.composition.api {
                match: "\\b(ref|reactive|computed|watch|watchEffect|onMounted|onUpdated|onUnmounted|provide|inject)\\b"
            },
            
            (raw_text) @script.props.definition {
                match: "\\bprops\\s*:\\s*\\{[^}]+\\}"
            },
            
            (raw_text) @script.emits.definition {
                match: "\\bemits\\s*:\\s*(\\[[^\\]]+\\]|\\{[^}]+\\})"
            }
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "script_patterns",
            "is_setup": "script.setup" in node["captures"] and any("setup" == attr.get("text", "") for attr in node["captures"].get("script.attr.name", [])),
            "lang": next((lang.get("text", "").strip('"\'') for lang in node["captures"].get("script.attr.lang", [])), "js"),
            "has_options_api": "script.options.api" in node["captures"],
            "has_composition_api": "script.composition.api" in node["captures"],
            "has_props": "script.props.definition" in node["captures"],
            "has_emits": "script.emits.definition" in node["captures"],
            "script_content": node["captures"].get("script.content", {}).get("text", ""),
            "script_type": (
                "setup" if "script.setup" in node["captures"] and any("setup" == attr.get("text", "") for attr in node["captures"].get("script.attr.name", [])) else
                "options_api" if "script.options.api" in node["captures"] else
                "composition_api" if "script.composition.api" in node["captures"] else
                "standard" if "script.content" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "template_expressions": {
        "pattern": """
        [
            (interpolation
                (raw_text) @expr.interpolation.text) @expr.interpolation,
                
            (directive_attribute
                name: (directive_name) @expr.directive.name
                value: (attribute_value) @expr.directive.value) @expr.directive,
                
            (directive_attribute
                name: (directive_name) @expr.binding.name {
                    match: "^v-bind$|^:"
                }
                argument: (directive_argument) @expr.binding.arg
                value: (attribute_value) @expr.binding.value) @expr.binding
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "template_expressions",
            "is_interpolation": "expr.interpolation" in node["captures"],
            "is_directive": "expr.directive" in node["captures"],
            "is_binding": "expr.binding" in node["captures"],
            "expression_text": (
                node["captures"].get("expr.interpolation.text", {}).get("text", "") or
                node["captures"].get("expr.directive.value", {}).get("text", "") or
                node["captures"].get("expr.binding.value", {}).get("text", "")
            ),
            "directive_name": node["captures"].get("expr.directive.name", {}).get("text", "") or node["captures"].get("expr.binding.name", {}).get("text", ""),
            "binding_argument": node["captures"].get("expr.binding.arg", {}).get("text", ""),
            "expression_type": (
                "interpolation" if "expr.interpolation" in node["captures"] else
                "binding" if "expr.binding" in node["captures"] else
                "directive" if "expr.directive" in node["captures"] else
                "unknown"
            )
        }
    }
}

VUE_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "component": QueryPattern(
                pattern="""
                (component
                    (template_element
                        (start_tag)
                        (_)* @syntax.component.template
                        (end_tag))
                    (script_element
                        (start_tag)
                        (_)? @syntax.component.script
                        (end_tag))
                    (style_element
                        (start_tag)
                        (_)? @syntax.component.style
                        (end_tag))) @syntax.component.def
                """,
                extract=lambda node: {
                    "type": "component"
                }
            ),
            "method": QueryPattern(
                pattern="""
                (script_element
                    (start_tag)
                    (raw_text) @syntax.method.body
                    (end_tag)) @syntax.method.def
                """
            )
        }
    },

    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "expression": QueryPattern(
                pattern="""
                [
                    (interpolation
                        (raw_text) @semantics.expression.value) @semantics.expression.def,
                    (directive_attribute
                        name: (directive_name) @semantics.expression.name
                        value: (attribute_value) @semantics.expression.value) @semantics.expression.def
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("semantics.expression.value", {}).get("text", "")
                }
            ),
            "variable": QueryPattern(
                pattern="""
                (attribute
                    name: (attribute_name) @semantics.variable.name
                    value: (attribute_value) @semantics.variable.value) @semantics.variable.def
                """
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "module": QueryPattern(
                pattern="""
                (template_element
                    (start_tag)
                    (_)* @structure.module.content
                    (end_tag)) @structure.module.def
                """
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
                pattern="""
                (comment) @documentation.comment
                """
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COMPONENT: {
            "component_structure": QueryPattern(
                pattern="""
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
                extract=lambda node: {
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
            )
        }
    },

    "REPOSITORY_LEARNING": VUE_PATTERNS_FOR_LEARNING
} 