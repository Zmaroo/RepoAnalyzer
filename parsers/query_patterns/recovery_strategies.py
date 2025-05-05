"""Recovery strategies for tree-sitter patterns.

This module provides strategy classes for error recovery in tree-sitter patterns,
extracted from TreeSitterResilientPattern to improve modularity.
"""

from typing import Dict, Any, List, Optional, Union
import re
import time
import asyncio
from abc import ABC, abstractmethod

from utils.logger import log
from parsers.query_patterns.tree_sitter_utils import execute_tree_sitter_query, regex_matches

class RecoveryStrategy(ABC):
    """Base class for pattern recovery strategies."""
    
    def __init__(self, name: str):
        """Initialize recovery strategy.
        
        Args:
            name: Strategy name
        """
        self.name = name
        self.metrics = {
            "attempts": 0,
            "successes": 0,
            "success_rate": 0.0,
            "avg_recovery_time": 0.0
        }
    
    async def apply(
        self,
        source_code: str,
        pattern_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply recovery strategy.
        
        Args:
            source_code: Source code to recover against
            pattern_name: Name of the pattern
            **kwargs: Additional arguments specific to the strategy
            
        Returns:
            Dict with recovery results
        """
        start_time = time.time()
        self.metrics["attempts"] += 1
        
        try:
            result = await self._apply_strategy(source_code, pattern_name, **kwargs)
            recovery_time = time.time() - start_time
            
            # Update metrics
            if result and result.get("success", False):
                self.metrics["successes"] += 1
                
                # Update average recovery time
                total_successes = self.metrics["successes"]
                prev_avg = self.metrics["avg_recovery_time"]
                self.metrics["avg_recovery_time"] = (
                    (prev_avg * (total_successes - 1) + recovery_time) / total_successes
                    if total_successes > 0 else recovery_time
                )
            
            # Update success rate
            if self.metrics["attempts"] > 0:
                self.metrics["success_rate"] = self.metrics["successes"] / self.metrics["attempts"]
                
            # Add strategy info to result
            if result:
                result["strategy"] = self.name
                result["recovery_time"] = recovery_time
                
            return result
            
        except Exception as e:
            await log(
                f"Error applying {self.name} recovery strategy: {e}",
                level="warning",
                context={"pattern_name": pattern_name}
            )
            return {
                "success": False,
                "error": str(e),
                "strategy": self.name
            }
    
    @abstractmethod
    async def _apply_strategy(
        self,
        source_code: str,
        pattern_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply strategy implementation (to be overridden by subclasses).
        
        Args:
            source_code: Source code to recover against
            pattern_name: Name of the pattern
            **kwargs: Additional arguments specific to the strategy
            
        Returns:
            Dict with recovery results
        """
        pass

class FallbackPatternStrategy(RecoveryStrategy):
    """Strategy that uses fallback tree-sitter patterns."""
    
    def __init__(self):
        """Initialize fallback pattern strategy."""
        super().__init__(name="fallback_patterns")
    
    async def _apply_strategy(
        self,
        source_code: str,
        pattern_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply fallback patterns strategy.
        
        Args:
            source_code: Source code to recover against
            pattern_name: Name of the pattern
            **kwargs: Must include tree_sitter_parser, fallback_patterns,
                      extract_fn (optional)
            
        Returns:
            Dict with recovery results
        """
        tree_sitter_parser = kwargs.get("tree_sitter_parser")
        fallback_patterns = kwargs.get("fallback_patterns", [])
        extract_fn = kwargs.get("extract_fn")
        
        if not tree_sitter_parser or not fallback_patterns:
            return {"success": False, "error": "Missing required parameters"}
        
        # Try each fallback pattern
        for idx, fallback_query in enumerate(fallback_patterns):
            # Execute query
            matches, _ = await execute_tree_sitter_query(
                source_code,
                tree_sitter_parser,
                fallback_query,
                extract_fn=extract_fn,
                is_fallback=True,
                fallback_index=idx,
                pattern_name=pattern_name
            )
            
            if matches:
                return {
                    "success": True,
                    "matches": matches,
                    "fallback_index": idx
                }
        
        return {"success": False, "error": "No fallback patterns matched"}

class RegexFallbackStrategy(RecoveryStrategy):
    """Strategy that falls back to regex pattern matching."""
    
    def __init__(self):
        """Initialize regex fallback strategy."""
        super().__init__(name="regex_fallback")
    
    async def _apply_strategy(
        self,
        source_code: str,
        pattern_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply regex fallback strategy.
        
        Args:
            source_code: Source code to recover against
            pattern_name: Name of the pattern
            **kwargs: Must include regex_pattern, extract_fn (optional)
            
        Returns:
            Dict with recovery results
        """
        regex_pattern = kwargs.get("regex_pattern")
        extract_fn = kwargs.get("extract_fn")
        
        if not regex_pattern:
            return {"success": False, "error": "Missing regex pattern"}
        
        matches = await regex_matches(
            source_code,
            regex_pattern,
            extract_fn=extract_fn,
            pattern_name=pattern_name
        )
        
        if matches:
            return {
                "success": True,
                "matches": matches,
                "fallback_type": "regex"
            }
        
        return {"success": False, "error": "Regex pattern did not match"}

class PartialMatchStrategy(RecoveryStrategy):
    """Strategy that attempts to match on segments of source code."""
    
    def __init__(self):
        """Initialize partial match strategy."""
        super().__init__(name="partial_match")
    
    async def _apply_strategy(
        self,
        source_code: str,
        pattern_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply partial match strategy.
        
        Args:
            source_code: Source code to recover against
            pattern_name: Name of the pattern
            **kwargs: Must include tree_sitter_parser, query,
                      extract_fn (optional)
            
        Returns:
            Dict with recovery results
        """
        tree_sitter_parser = kwargs.get("tree_sitter_parser")
        query = kwargs.get("query")
        extract_fn = kwargs.get("extract_fn")
        
        if not tree_sitter_parser or not query:
            return {"success": False, "error": "Missing required parameters"}
        
        # Break down source into lines
        lines = source_code.split('\n')
        
        # Create sliding window of increasing size
        window_size = 5  # Start with 5 lines
        max_window_size = min(20, len(lines))  # Cap at 20 lines or source length
        
        all_matches = []
        
        # Try different window sizes
        while window_size <= max_window_size and not all_matches:
            # Slide window over source
            for i in range(0, len(lines) - window_size + 1, window_size // 2):
                window = '\n'.join(lines[i:i+window_size])
                
                # Try to match this window
                matches, _ = await execute_tree_sitter_query(
                    window,
                    tree_sitter_parser,
                    query,
                    extract_fn=extract_fn,
                    is_fallback=True,
                    pattern_name=pattern_name
                )
                
                if matches:
                    # Add window information to matches
                    for match in matches:
                        match["partial_match"] = True
                        match["window_start_line"] = i
                        match["window_end_line"] = i + window_size
                        
                        # Adjust byte positions for captures
                        window_start_byte = sum(len(line) + 1 for line in lines[:i])
                        for capture_list in match.get("captures", {}).values():
                            for capture in capture_list:
                                if "start_byte" in capture:
                                    capture["start_byte"] += window_start_byte
                                if "end_byte" in capture:
                                    capture["end_byte"] += window_start_byte
                        
                    all_matches.extend(matches)
            
            # Increase window size
            window_size *= 2
        
        if all_matches:
            return {
                "success": True,
                "matches": all_matches,
                "partial_match": True
            }
        
        return {"success": False, "error": "No partial matches found"}

# Get available recovery strategies
def get_recovery_strategies() -> Dict[str, RecoveryStrategy]:
    """Get all available recovery strategies.
    
    Returns:
        Dict of recovery strategies
    """
    return {
        "fallback_patterns": FallbackPatternStrategy(),
        "regex_fallback": RegexFallbackStrategy(),
        "partial_match": PartialMatchStrategy()
    } 