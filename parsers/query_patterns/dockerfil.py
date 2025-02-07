"""Dockerfile-specific Tree-sitter patterns."""

DOCKERFILE_PATTERNS = {
    # From instruction patterns
    "from": """
        [
          (from_instruction
            image: (image_spec
              name: (image_name) @from.image.name
              tag: (image_tag)? @from.image.tag
              digest: (image_digest)? @from.image.digest) @from.image
            alias: (image_alias)? @from.alias) @from
        ]
    """,

    # Run instruction patterns
    "run": """
        [
          (run_instruction
            (shell_command) @run.shell
            (mount_param)* @run.mounts
            (param)* @run.params) @run,
          (run_instruction
            (json_string_array) @run.exec) @run.json
        ]
    """,

    # Copy/Add instruction patterns
    "copy": """
        [
          (copy_instruction
            (param)* @copy.params
            (path)* @copy.paths
            (heredoc_block)? @copy.heredoc) @copy,
          (add_instruction
            (param)* @add.params
            (path)* @add.paths
            (heredoc_block)? @add.heredoc) @add
        ]
    """,

    # Environment patterns
    "env": """
        [
          (env_instruction
            (env_pair
              name: (unquoted_string) @env.key
              value: (_)? @env.value)*) @env
        ]
    """,

    # Arg patterns
    "arg": """
        [
          (arg_instruction
            name: (unquoted_string) @arg.name
            default: (_)? @arg.default) @arg
        ]
    """,

    # Workdir patterns
    "workdir": """
        [
          (workdir_instruction
            (path) @workdir.path) @workdir
        ]
    """,

    # Expose patterns
    "expose": """
        [
          (expose_instruction
            (expose_port) @expose.port
            (expansion)* @expose.vars) @expose
        ]
    """,

    # Volume patterns
    "volume": """
        [
          (volume_instruction
            (path)* @volume.paths
            (json_string_array)? @volume.json) @volume
        ]
    """,

    # User patterns
    "user": """
        [
          (user_instruction
            user: (unquoted_string) @user.name
            group: (unquoted_string)? @user.group) @user
        ]
    """,

    # Label patterns
    "label": """
        [
          (label_instruction
            (label_pair
              key: (_) @label.key
              value: (_) @label.value)*) @label
        ]
    """,

    # Entrypoint/CMD patterns
    "entrypoint_cmd": """
        [
          (entrypoint_instruction
            (json_string_array) @entrypoint.exec) @entrypoint,
          (entrypoint_instruction
            (shell_command) @entrypoint.shell) @entrypoint,
          (cmd_instruction
            (json_string_array) @cmd.exec) @cmd,
          (cmd_instruction
            (shell_command) @cmd.shell) @cmd
        ]
    """,

    # Health check patterns
    "healthcheck": """
        [
          (healthcheck_instruction
            (param)* @health.params
            (cmd_instruction)? @health.cmd) @health
        ]
    """,

    # Shell patterns
    "shell": """
        [
          (shell_instruction
            (json_string_array) @shell.command) @shell
        ]
    """,

    # Onbuild patterns
    "onbuild": """
        [
          (onbuild_instruction
            (_) @onbuild.instruction) @onbuild
        ]
    """,

    # String patterns
    "string": """
        [
          (double_quoted_string) @string.double,
          (single_quoted_string) @string.single,
          (unquoted_string) @string.unquoted
        ]
    """,

    # Variable expansion patterns
    "expansion": """
        [
          (expansion
            (variable) @expansion.var) @expansion
        ]
    """,

    # Documentation patterns
    "documentation": """
        [
          (comment) @doc.comment
        ]
    """
} 