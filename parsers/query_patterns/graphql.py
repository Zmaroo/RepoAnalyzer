"""
GraphQL-specific query patterns for our custom GraphQL parser.
These patterns target the custom AST produced by our GraphQL parser.
"""

GRAPHQL_PATTERNS = [
    # Capture all GraphQL definitions (e.g. type, interface, enum, etc.)
    "(graphql (definition) @definition)",
    # Optionally capture the name inside the definition
    "(definition (name) @definition.name)"
] 