"""
Query patterns for requirements.txt files.

These patterns target the 'package' nodes extracted from a requirements file.
"""

REQUIREMENTS_PATTERNS = {
    # Package requirement patterns
    "requirement": """
        [
          (requirement
            package: (package) @req.name
            version_spec: (version_spec
              version_cmp: (version_cmp) @req.version.operator
              version: (version) @req.version.number)? @req.version
            url_spec: (url_spec
              url: (url) @req.url)? @req.url_spec
            marker_spec: (marker_spec
              marker_var: (marker_var) @req.marker.var
              marker_op: (marker_op) @req.marker.op
              (quoted_string)? @req.marker.value)? @req.marker
            extras: (extras
              package: (package)* @req.extras.package)? @req.extras) @req.def
        ]
    """,

    # Global option patterns
    "global_opt": """
        [
          (global_opt
            option: (option) @opt.name
            [
              (argument) @opt.arg
              (quoted_string) @opt.string
              (path) @opt.path
              (url) @opt.url
            ]*) @opt.def
        ]
    """,

    # Environment variable patterns
    "env_var": """
        [
          (env_var) @env.var
        ]
    """,

    # URL patterns
    "url": """
        [
          (url
            env_var: (env_var)* @url.env_var) @url.def
        ]
    """,

    # File structure patterns
    "file": """
        [
          (file
            [
              (requirement) @file.requirement
              (global_opt) @file.global_opt
              (comment) @file.comment
              (path) @file.path
              (url) @file.url
            ]*) @file.def
        ]
    """,

    # Comment patterns
    "comment": """
        [
          (comment) @comment
        ]
    """,

    "semantics": {
        "variable": [
            """
            (requirement
                package: (package) @name
                version_spec: (version_spec)? @version) @variable
            """
        ]
    },

    "structure": {
        "import": [
            """
            (requirement
                url_spec: (url_spec)? @url) @import
            """
        ]
    },

    "documentation": {
        "comment": [
            """
            (comment) @comment
            """
        ]
    }
}