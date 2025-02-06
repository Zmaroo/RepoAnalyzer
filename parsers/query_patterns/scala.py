"""Scala-specific Tree-sitter patterns."""

SCALA_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
          (method_definition)
          (anonymous_function)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_definition
            modifiers: (modifiers)? @function.modifiers
             name: (identifier) @function.name
            type_parameters: (type_parameter_list)? @function.type_params
            parameters: (parameter_list
              (parameter
                modifiers: (modifiers)? @function.param.modifiers
                name: (identifier) @function.param.name
                type: (_) @function.param.type
                default: (_)? @function.param.default)*) @function.params
            return_type: (_)? @function.return_type
            body: (block) @function.body) @function.def,
          (method_definition
            modifiers: (modifiers)? @function.modifiers
             name: (identifier) @function.name
            type_parameters: (type_parameter_list)? @function.type_params
            parameters: (parameter_list) @function.params
            return_type: (_)? @function.return_type
            body: (block) @function.body) @function.def,
          (anonymous_function
             parameters: (parameter_list)? @function.params
            body: (_) @function.body) @function.lambda
        ]
    """,
    # Class patterns
    "class": """
        [
          (class_definition
            modifiers: (modifiers)? @class.modifiers
            name: (identifier) @class.name
            type_parameters: (type_parameter_list)? @class.type_params
            constructor_parameters: (constructor_parameter_list
              (parameter
                modifiers: (modifiers)? @class.param.modifiers
                name: (identifier) @class.param.name
                type: (_) @class.param.type)*) @class.params
            extends_clause: (extends_clause)? @class.extends
            with_clause: (with_clause)? @class.with
            body: (template_body
              [
                (function_definition)* @class.methods
                (value_definition)* @class.values
                (variable_definition)* @class.vars
                (type_definition)* @class.types
              ]) @class.body) @class.def,
          (trait_definition
            modifiers: (modifiers)? @trait.modifiers
            name: (identifier) @trait.name
            type_parameters: (type_parameter_list)? @trait.type_params
            extends_clause: (extends_clause)? @trait.extends
            with_clause: (with_clause)? @trait.with
            body: (template_body) @trait.body) @trait.def,
          (object_definition
            modifiers: (modifiers)? @object.modifiers
            name: (identifier) @object.name
            extends_clause: (extends_clause)? @object.extends
            with_clause: (with_clause)? @object.with
            body: (template_body) @object.body) @object.def,
          (case_class_definition
            modifiers: (modifiers)? @case_class.modifiers
            name: (identifier) @case_class.name
            type_parameters: (type_parameter_list)? @case_class.type_params
            parameters: (constructor_parameter_list) @case_class.params
            extends_clause: (extends_clause)? @case_class.extends
            with_clause: (with_clause)? @case_class.with
            body: (template_body)? @case_class.body) @case_class.def
        ]
    """,
    # Package patterns
    "package": """
        [
          (package_clause
            name: (qualified_name) @package.name) @package,
          (package_object
            name: (identifier) @package.object.name
            body: (template_body) @package.object.body) @package.object
        ]
    """,
    # Import patterns
    "import": """
        [
          (import_declaration
            importers: (import_selectors
              (import_selector
                name: (identifier) @import.name
                rename: (identifier)? @import.rename)*) @import.selectors) @import,
          (import_expression
            qualifier: (qualified_name) @import.qualifier
            selectors: (import_selectors)? @import.selectors) @import.expr
        ]
    """,
    # Type patterns
    "type": """
        [
          (type_definition
            modifiers: (modifiers)? @type.modifiers
            name: (identifier) @type.name
            type_parameters: (type_parameter_list)? @type.params
            body: (_) @type.body) @type.def,
          (type_projection
            type: (_) @type.proj.type) @type.projection,
          (existential_type
            type: (_) @type.exist.type
            declarations: (existential_declarations) @type.exist.decls) @type.existential,
          (compound_type
            types: (_)* @type.compound.types) @type.compound
        ]
    """,
    # Pattern matching patterns
    "pattern_matching": """
        [
          (match_expression
            expression: (_) @match.expr
            cases: (case_clause
              pattern: (_) @case.pattern
              guard: (_)? @case.guard
              body: (_) @case.body)*) @match,
          (pattern_definition
            pattern: (_) @pattern.pattern
            type: (_)? @pattern.type
            body: (_) @pattern.body) @pattern
        ]
    """,
    # For comprehension patterns
    "for_comprehension": """
        [
          (for_expression
            enumerators: (enumerators
              (generator
                pattern: (_) @for.pattern
                expression: (_) @for.expr)*
              (guard)* @for.guard) @for.enums
            body: (_) @for.body) @for
        ]
    """,
    # Implicit patterns
    "implicit": """
        [
          (function_definition
            modifiers: (modifiers
              (modifier) @implicit.modifier
              (#eq? @implicit.modifier "implicit")) @implicit.modifiers) @implicit.function,
          (class_definition
            modifiers: (modifiers
              (modifier) @implicit.modifier
              (#eq? @implicit.modifier "implicit")) @implicit.modifiers) @implicit.class,
          (parameter
            modifiers: (modifiers
              (modifier) @implicit.modifier
              (#eq? @implicit.modifier "implicit")) @implicit.modifiers) @implicit.param
        ]
    """,
    # Annotation patterns
    "annotation": """
        [
          (annotation
            name: (identifier) @annotation.name
            arguments: (argument_list)? @annotation.args) @annotation
        ]
    """,
    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.line,
          (multi_line_comment) @doc.block,
          (scaladoc) @doc.scaladoc
        ]
    """
} 