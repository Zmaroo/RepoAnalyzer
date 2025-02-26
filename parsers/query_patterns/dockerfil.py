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

# Repository learning patterns for Dockerfile
DOCKERFILE_PATTERNS_FOR_LEARNING = {
    "base_image_usage": {
        "pattern": """
        [
            (from_instruction
                image: (image_spec
                    name: (image_name) @base.image.name
                    tag: (image_tag)? @base.image.tag
                    digest: (image_digest)? @base.image.digest) @base.image) @base.from
        ]
        """,
        "extract": lambda node: {
            "type": "base_image_pattern",
            "image_name": node["captures"].get("base.image.name", {}).get("text", ""),
            "image_tag": node["captures"].get("base.image.tag", {}).get("text", ""),
            "uses_specific_tag": node["captures"].get("base.image.tag", {}).get("text", "") not in ["", "latest"],
            "uses_digest": "base.image.digest" in node["captures"],
            "is_official_image": not "/" in node["captures"].get("base.image.name", {}).get("text", ""),
            "is_alpine": "alpine" in (node["captures"].get("base.image.name", {}).get("text", "") + 
                                    node["captures"].get("base.image.tag", {}).get("text", "")).lower(),
            "is_slim": "slim" in (node["captures"].get("base.image.tag", {}).get("text", "") or "").lower()
        }
    },
    
    "layer_optimization": {
        "pattern": """
        [
            (run_instruction
                (shell_command) @layer.run.command) @layer.run,
                
            (run_instruction
                (shell_command
                    (shell_fragment) @layer.run.multiline
                    (#match? @layer.run.multiline ".*\\\\.*")) @layer.run.command) @layer.run.multi
        ]
        """,
        "extract": lambda node: {
            "type": "layer_optimization_pattern",
            "uses_multi_line": "layer.run.multi" in node["captures"],
            "uses_apt_get": "apt-get" in (node["captures"].get("layer.run.command", {}).get("text", "") or "").lower(),
            "clears_cache": ("rm -rf /var/lib/apt/lists/*" in (node["captures"].get("layer.run.command", {}).get("text", "") or "") or
                          "apt-get clean" in (node["captures"].get("layer.run.command", {}).get("text", "") or "")),
            "combines_commands": "&&" in (node["captures"].get("layer.run.command", {}).get("text", "") or ""),
            "uses_curl_or_wget": any(cmd in (node["captures"].get("layer.run.command", {}).get("text", "") or "").lower() 
                                   for cmd in ["curl", "wget"])
        }
    },
    
    "multi_stage_builds": {
        "pattern": """
        [
            (from_instruction
                image: (image_spec) @multistage.image
                alias: (image_alias) @multistage.alias) @multistage.with_alias,
                
            (from_instruction
                image: (image_spec
                    name: (image_name) @multistage.copy.source) @multistage.image) @multistage.from,
                
            (copy_instruction
                sources: (_)+ @multistage.copy.sources
                destination: (_) @multistage.copy.dest
                flags: (param
                    (param_name) @multistage.copy.flag.name
                    (#match? @multistage.copy.flag.name "^--from$")
                    (param_value) @multistage.copy.flag.value)?) @multistage.copy
        ]
        """,
        "extract": lambda node: {
            "type": "multi_stage_build_pattern",
            "has_alias": "multistage.alias" in node["captures"],
            "uses_copy_from": "multistage.copy.flag.name" in node["captures"] and 
                            node["captures"].get("multistage.copy.flag.name", {}).get("text", "") == "--from",
            "alias_name": node["captures"].get("multistage.alias", {}).get("text", ""),
            "copy_source": node["captures"].get("multistage.copy.flag.value", {}).get("text", "")
        }
    },
    
    "dockerfile_best_practices": {
        "pattern": """
        [
            (user_instruction
                user: (_) @practice.user.name) @practice.user,
                
            (workdir_instruction
                path: (_) @practice.workdir.path) @practice.workdir,
                
            (expose_instruction
                ports: (expose_port)+ @practice.expose.ports) @practice.expose,
                
            (healthcheck_instruction
                command: (shell_command) @practice.health.command) @practice.health,
                
            (volume_instruction
                path: (_)+ @practice.volume.path) @practice.volume
        ]
        """,
        "extract": lambda node: {
            "type": "dockerfile_best_practice_pattern",
            "sets_user": "practice.user" in node["captures"],
            "sets_workdir": "practice.workdir" in node["captures"],
            "exposes_ports": "practice.expose" in node["captures"],
            "uses_healthcheck": "practice.health" in node["captures"],
            "uses_volumes": "practice.volume" in node["captures"],
            "user_name": node["captures"].get("practice.user.name", {}).get("text", ""),
            "is_root_user": node["captures"].get("practice.user.name", {}).get("text", "").lower() in ["0", "root"]
        }
    }
}

# Add the repository learning patterns to the main patterns
DOCKERFILE_PATTERNS['REPOSITORY_LEARNING'] = DOCKERFILE_PATTERNS_FOR_LEARNING 