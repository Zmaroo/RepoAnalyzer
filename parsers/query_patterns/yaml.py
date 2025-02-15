"""
Custom YAML query patterns.

These patterns traverse the custom AST produced by our custom YAML parser.
The AST's root should be of type "yaml_stream", and its children might be
mapped as "mapping", "sequence", or "scalar" nodes. Adjust these queries as needed.
"""

YAML_PATTERNS = [
    # Capture YAML mappings
    "(yaml_stream (mapping) @mapping)",
    # Capture YAML sequences
    "(yaml_stream (sequence) @sequence)",
    # Capture YAML scalars (for values)
    "(yaml_stream (scalar) @scalar)",
] 