MAKEFILE_PATTERNS = {
    "rule": """
        [
          (rule
            targets: (_) @rule.targets
            prerequisites: (_)? @rule.prerequisites
            recipe: (_)* @rule.recipe) @rule,
          (variable_definition
            name: (_) @variable.name
            value: (_) @variable.value) @variable
        ]
    """
}