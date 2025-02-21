def encode_query_pattern(pattern):
    """
    Encodes a query pattern to bytes if it's a string.
    Otherwise returns the pattern unchanged.
    """
    if isinstance(pattern, str):
        return pattern.encode('utf-8')
    return pattern

def encode_query_patterns(patterns):
    """
    Recursively encodes all strings in the query patterns structure to bytes.
    If a value is already bytes, or not a string/dict/list then it is returned unchanged.
    """
    if isinstance(patterns, str):
        return patterns.encode('utf-8')
    elif isinstance(patterns, dict):
        return {key: encode_query_patterns(value) for key, value in patterns.items()}
    elif isinstance(patterns, list):
        return [encode_query_patterns(item) for item in patterns]
    else:
        return patterns 