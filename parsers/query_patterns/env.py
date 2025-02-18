"""
Query patterns for .env files.

The parser produces an AST with a root node 'env_file' and children of type 'env_var'.
"""

ENV_PATTERNS = {
    "variable": """
        [
          (env_file (env_var) @env_var)
        ]
    """
} 