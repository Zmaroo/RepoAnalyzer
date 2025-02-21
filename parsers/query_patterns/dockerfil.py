"""Query patterns for Dockerfile files."""

from .common import COMMON_PATTERNS

DOCKERFILE_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "instruction": {
            "pattern": """
            [
                (from_instruction
                    image: (image_spec
                        name: (image_name) @syntax.from.image.name
                        tag: (image_tag)? @syntax.from.image.tag
                        digest: (image_digest)? @syntax.from.image.digest) @syntax.from.image
                    alias: (image_alias)? @syntax.from.alias) @syntax.from,
                    
                (run_instruction
                    (shell_command) @syntax.run.shell
                    (mount_param)* @syntax.run.mounts
                    (param)* @syntax.run.params) @syntax.run,
                    
                (env_instruction
                    (env_pair
                        name: (unquoted_string) @syntax.env.key
                        value: (_)? @syntax.env.value)*) @syntax.env
            ]
            """,
            "extract": lambda node: {
                "type": ("from" if "syntax.from" in node["captures"] else
                        "run" if "syntax.run" in node["captures"] else "env")
            }
        }
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
        "variable": {
            "pattern": """
            [
                (env_instruction
                    (env_pair
                        name: (unquoted_string) @semantics.var.name
                        value: (_)? @semantics.var.value)*) @semantics.var.def,
                        
                (arg_instruction
                    name: (unquoted_string) @semantics.arg.name
                    default: (_)? @semantics.arg.default) @semantics.arg.def
            ]
            """,
            "extract": lambda node: {
                "name": (node["captures"].get("semantics.var.name", {}).get("text", "") or
                        node["captures"].get("semantics.arg.name", {}).get("text", "")),
                "type": "env" if "semantics.var.def" in node["captures"] else "arg"
            }
        }
    },

    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "")
            }
        }
    }
} 