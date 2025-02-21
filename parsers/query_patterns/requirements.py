"""
Query patterns for requirements.txt files.

These patterns target the 'package' nodes extracted from a requirements file.
"""

REQUIREMENTS_PATTERNS = {
    "syntax": {
        "requirement": {
            "pattern": """
            [
                (requirement
                    package: (package) @syntax.requirement.name
                    version_spec: (version_spec
                        version_cmp: (version_cmp) @syntax.requirement.version.operator
                        version: (version) @syntax.requirement.version.number)? @syntax.requirement.version
                    extras: (extras
                        package: (package)* @syntax.requirement.extras.package)? @syntax.requirement.extras
                    marker_spec: (marker_spec
                        marker_var: (marker_var) @syntax.requirement.marker.var
                        marker_op: (marker_op) @syntax.requirement.marker.op
                        (quoted_string)? @syntax.requirement.marker.value)? @syntax.requirement.marker) @syntax.requirement.def,
                
                (requirement_opt
                    option: (option) @syntax.requirement.option.name
                    value: [(argument) (quoted_string)] @syntax.requirement.option.value) @syntax.requirement.option.def
            ]
            """
        }
    },
    "structure": {
        "file": {
            "pattern": """
            [
                (file
                    [(requirement) (global_opt) (comment) (path) (url)]* @structure.file.content) @structure.file.def,
                
                (global_opt
                    option: (option) @structure.option.name
                    [(argument) (quoted_string) (path) (url)]* @structure.option.value) @structure.option.def
            ]
            """
        },
        "url": {
            "pattern": """
            [
                (url_spec
                    url: (url
                        env_var: (env_var)* @structure.url.env_var) @structure.url.value) @structure.url.def,
                
                (path) @structure.path
            ]
            """
        }
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (env_var) @semantics.variable.env,
                (marker_var) @semantics.variable.marker
            ]
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (linebreak
                    comment: (comment) @documentation.comment.inline) @documentation.comment.line
            ]
            """
        }
    }
}