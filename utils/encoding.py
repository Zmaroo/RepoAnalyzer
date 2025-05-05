"""Encoding utilities for query patterns."""

from typing import Dict, List, Union, Any
from utils.error_handling import handle_async_errors, AsyncErrorBoundary

@handle_async_errors()
async def encode_query_pattern(pattern: Union[str, bytes]) -> Union[str, bytes]:
    """
    Encodes a query pattern to bytes if it's a string.
    Otherwise returns the pattern unchanged.
    
    Args:
        pattern: The pattern to encode
        
    Returns:
        The encoded pattern
    """
    async with AsyncErrorBoundary("encoding query pattern"):
        if isinstance(pattern, str):
            return pattern.encode('utf-8')
        return pattern

@handle_async_errors()
async def encode_query_patterns(patterns: Union[str, bytes, Dict, List]) -> Union[str, bytes, Dict, List]:
    """
    Recursively encodes all strings in the query patterns structure to bytes.
    If a value is already bytes, or not a string/dict/list then it is returned unchanged.
    
    Args:
        patterns: The patterns structure to encode
        
    Returns:
        The encoded patterns structure
    """
    async with AsyncErrorBoundary("encoding query patterns"):
        if isinstance(patterns, str):
            return patterns.encode('utf-8')
        elif isinstance(patterns, dict):
            return {key: await encode_query_patterns(value) for key, value in patterns.items()}
        elif isinstance(patterns, list):
            return [await encode_query_patterns(item) for item in patterns]
        else:
            return patterns 