"""Tree-sitter pattern utilities for RepoAnalyzer.

This module provides utility functions for tree-sitter pattern processing,
extracted from the enhanced_patterns.py to improve code organization and reuse.
"""

from typing import Dict, Any, List, Optional, Set, Union
import time
import asyncio
from utils.logger import log

async def count_nodes(node) -> int:
    """Count nodes in a tree-sitter AST recursively.
    
    Args:
        node: Tree-sitter node to count
        
    Returns:
        int: Total node count
    """
    if not node:
        return 0
        
    count = 1  # Count this node
    
    # Count children recursively
    for child in node.children:
        count += count_nodes(child)
        
    return count

async def execute_tree_sitter_query(
    source_code: str,
    tree_sitter_parser: Any,
    query: Any,
    timeout_micros: int = 5000,
    match_limit: Optional[int] = None,
    extract_fn: Optional[callable] = None,
    is_fallback: bool = False,
    fallback_index: Optional[int] = None,
    pattern_name: str = "unnamed_pattern"
) -> List[Dict[str, Any]]:
    """Execute a tree-sitter query against source code.
    
    Args:
        source_code: Source code to match against
        tree_sitter_parser: Tree-sitter parser instance
        query: Tree-sitter query object
        timeout_micros: Timeout in microseconds
        match_limit: Maximum number of matches to return
        extract_fn: Optional function to extract structured data from matches
        is_fallback: Whether this is a fallback query
        fallback_index: Index of the fallback pattern if applicable
        pattern_name: Name of the pattern
        
    Returns:
        List of matches with extracted information
    """
    if not query or not tree_sitter_parser:
        return []
        
    try:
        # Parse the source code with tree-sitter
        tree = tree_sitter_parser.parse(source_code)
        
        if not tree or not tree.root_node:
            return []
        
        # Configure query parameters
        kwargs = {"timeout_micros": timeout_micros}
        if match_limit is not None:
            kwargs["match_limit"] = match_limit
            
        # Execute query
        query_start_time = time.time()
        query_matches = query.matches(
            tree.root_node,
            source_code.encode(),
            **kwargs
        )
        query_time = time.time() - query_start_time
        
        # Check for exceeding limits
        exceeded_match_limit = getattr(query, "did_exceed_match_limit", False)
        
        # Convert query matches to result format
        matches = []
        for match in query_matches:
            match_data = {
                "match_id": match.id,
                "pattern_index": match.pattern_index,
                "captures": {},
                "node": match.captures[0].node if match.captures else None
            }
            
            if is_fallback:
                match_data["is_fallback"] = is_fallback
                match_data["fallback_index"] = fallback_index
            
            # Extract captures
            for capture in match.captures:
                name = query.capture_names[capture.index]
                if name not in match_data["captures"]:
                    match_data["captures"][name] = []
                
                node_data = {
                    "text": source_code[capture.node.start_byte:capture.node.end_byte],
                    "start_point": list(capture.node.start_point),
                    "end_point": list(capture.node.end_point),
                    "start_byte": capture.node.start_byte,
                    "end_byte": capture.node.end_byte,
                    "type": capture.node.type
                }
                
                match_data["captures"][name].append(node_data)
            
            # Apply extraction if provided
            if extract_fn:
                try:
                    extracted = extract_fn(match_data)
                    if extracted:
                        match_data.update(extracted)
                except Exception as e:
                    await log(
                        f"Error in extraction: {e}",
                        level="warning",
                        context={
                            "pattern_name": pattern_name,
                            "is_fallback": is_fallback,
                            "fallback_index": fallback_index
                        }
                    )
            
            matches.append(match_data)
        
        # Collect query metrics
        metrics = {
            "query_time": query_time,
            "node_count": await count_nodes(tree.root_node),
            "capture_count": sum(len(m["captures"]) for m in matches),
            "exceeded_match_limit": exceeded_match_limit,
            "exceeded_time_limit": False
        }
            
        return matches, metrics
        
    except Exception as e:
        await log(
            f"Error in tree-sitter query execution: {e}",
            level="warning" if is_fallback else "error",
            context={
                "pattern_name": pattern_name,
                "is_fallback": is_fallback,
                "fallback_index": fallback_index
            }
        )
        return [], {}

async def extract_captures(
    match_data: Dict[str, Any],
    source_code: str,
    extract_fn: Optional[callable] = None
) -> Dict[str, Any]:
    """Extract and process captures from a match.
    
    Args:
        match_data: Match data containing captures
        source_code: Source code
        extract_fn: Optional function to extract structured data
        
    Returns:
        Processed match data
    """
    if not match_data or "captures" not in match_data:
        return match_data
        
    try:
        # Process captures
        for capture_name, captures in match_data["captures"].items():
            for i, capture in enumerate(captures):
                # Add text if not present
                if "text" not in capture and "start_byte" in capture and "end_byte" in capture:
                    capture["text"] = source_code[capture["start_byte"]:capture["end_byte"]]
                    
        # Apply extraction if provided
        if extract_fn:
            extracted = extract_fn(match_data)
            if extracted:
                match_data.update(extracted)
                
        return match_data
        
    except Exception as e:
        await log(
            f"Error extracting captures: {e}",
            level="warning"
        )
        return match_data

async def regex_matches(
    source_code: str,
    regex_pattern: str,
    extract_fn: Optional[callable] = None,
    pattern_name: str = "unnamed_pattern"
) -> List[Dict[str, Any]]:
    """Match using regex pattern.
    
    Args:
        source_code: Source code to match against
        regex_pattern: Regex pattern string
        extract_fn: Optional function to extract structured data
        pattern_name: Name of the pattern
        
    Returns:
        List of matches
    """
    if not regex_pattern:
        return []
        
    try:
        import re
        pattern = re.compile(regex_pattern, re.MULTILINE | re.DOTALL)
        
        matches = []
        for match in pattern.finditer(source_code):
            match_data = {
                "match": match,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
                "groups": match.groups(),
                "named_groups": match.groupdict(),
                "is_fallback": True,
                "fallback_type": "regex"
            }
            
            if extract_fn:
                try:
                    extracted = extract_fn(match)
                    if extracted:
                        match_data.update(extracted)
                except Exception as e:
                    await log(
                        f"Error in regex extraction: {e}",
                        level="warning",
                        context={
                            "pattern_name": pattern_name
                        }
                    )
            
            matches.append(match_data)
            
        return matches
    except Exception as e:
        await log(
            f"Error in regex matching: {e}",
            level="warning",
            context={
                "pattern_name": pattern_name
            }
        )
        return [] 