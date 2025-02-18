"""Query patterns for Dockerfile files."""

DOCKERFILE_PATTERNS = {
    "syntax": {
        "function": [
            """
            (run_instruction
                (shell_command) @run.shell
                (mount_param)* @run.mounts
                (param)* @run.params) @function
            """
        ]
    },
    "structure": {
        "import": [
            """
            (from_instruction
                image: (image_spec
                    name: (image_name) @from.image.name
                    tag: (image_tag)? @from.image.tag
                    digest: (image_digest)? @from.image.digest) @from.image
                alias: (image_alias)? @from.alias) @import
            """
        ]
    },
    "semantics": {
        "variable": [
            """
            (env_instruction
                (env_pair
                    name: (unquoted_string) @env.key
                    value: (_)? @env.value)*) @variable
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