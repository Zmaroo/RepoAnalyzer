"""Learning strategies for tree-sitter patterns.

This module provides strategy classes for learning and improving tree-sitter patterns,
extracted from TreeSitterCrossProjectPatternLearner to improve extensibility.
"""

from typing import Dict, Any, List, Optional, Union
import re
from collections import defaultdict
import asyncio
import time
import os
import json

from utils.logger import log
from parsers.types import PatternCategory, PatternPurpose

class BaseLearningStrategy:
    """Base class for pattern learning strategies."""
    
    def __init__(self, name: str):
        """Initialize learning strategy.
        
        Args:
            name: Strategy name
        """
        self.name = name
        self.metrics = {
            "attempts": 0,
            "improvements": 0,
            "improvement_rate": 0.0,
            "confidence_change": 0.0
        }
    
    async def apply(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Apply learning strategy to improve a pattern.
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Pattern insights
            language_id: Language identifier
            
        Returns:
            Improved pattern data or None
        """
        self.metrics["attempts"] += 1
        try:
            result = await self._apply_strategy(pattern, insights, language_id)
            
            if result:
                self.metrics["improvements"] += 1
                self.metrics["confidence_change"] += result.get("confidence", 0) - insights.get("pattern_confidence", 0.5)
                
            # Update improvement rate
            if self.metrics["attempts"] > 0:
                self.metrics["improvement_rate"] = self.metrics["improvements"] / self.metrics["attempts"]
                
            return result
            
        except Exception as e:
            await log(
                f"Error applying {self.name} learning strategy: {e}",
                level="warning",
                context={"language_id": language_id}
            )
            return None
    
    async def _apply_strategy(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Apply learning strategy logic (to be implemented by subclasses).
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Pattern insights
            language_id: Language identifier
            
        Returns:
            Improved pattern data or None
        """
        raise NotImplementedError("Subclasses must implement this method")

class NodePatternImprovement(BaseLearningStrategy):
    """Improves node pattern structure based on insights."""
    
    def __init__(self):
        """Initialize node pattern improvement strategy."""
        super().__init__(name="node_pattern_improvement")
    
    async def _apply_strategy(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Improve node pattern structure based on insights.
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Insights collected for the pattern
            language_id: Language ID
            
        Returns:
            Dictionary with improved pattern and confidence if improved
        """
        if not insights.get("node_type_frequencies"):
            return None
        
        # Find most common node types
        common_nodes = sorted(
            insights["node_type_frequencies"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 most common
        
        # Check if pattern can be improved with more specific node types
        generic_node_matches = re.findall(r"\([\._]\)", pattern)
        
        if not generic_node_matches:
            return None
        
        improved_pattern = pattern
        confidence = insights.get("pattern_confidence", 0.5)
        
        # Try to replace generic nodes with specific types
        for generic_node in generic_node_matches:
            if common_nodes:
                most_common = common_nodes[0][0]
                # Replace only one instance at a time to avoid overfitting
                improved_pattern = improved_pattern.replace(
                    generic_node, 
                    f"({most_common})", 
                    1
                )
                # Slight confidence boost
                confidence += 0.05
        
        return {
            "pattern": improved_pattern,
            "confidence": min(confidence, 0.95)  # Cap at 0.95
        }

class CaptureOptimization(BaseLearningStrategy):
    """Optimizes captures in the pattern based on insights."""
    
    def __init__(self):
        """Initialize capture optimization strategy."""
        super().__init__(name="capture_optimization")
    
    async def _apply_strategy(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Optimize captures in the pattern based on insights.
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Insights collected for the pattern
            language_id: Language ID
            
        Returns:
            Dictionary with improved pattern and confidence if improved
        """
        if not insights.get("capture_frequencies"):
            return None
        
        # Find captures that were rarely used
        rare_captures = [
            name for name, count in insights["capture_frequencies"].items()
            if count < 3  # Used less than 3 times
        ]
        
        if not rare_captures:
            return None
        
        improved_pattern = pattern
        confidence = insights.get("pattern_confidence", 0.5)
        
        # Remove rare captures while preserving the node patterns
        for capture in rare_captures:
            # Replace @capture with nothing (removes the capture but keeps the node)
            improved_pattern = re.sub(
                r"@" + re.escape(capture) + r"\b", 
                "", 
                improved_pattern
            )
        
        # Add captures for common structure patterns that aren't captured yet
        common_structures = sorted(
            insights["structure_frequencies"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]  # Top 3 most common
        
        for structure, count in common_structures:
            if count >= 5:  # Used at least 5 times
                capture_name, node_type = structure.split(":")
                # Check if node type exists without capture
                node_pattern = f"({node_type})"
                capture_pattern = f"({node_type}) @{capture_name}"
                
                # Add capture if node exists without capture
                if node_pattern in improved_pattern and capture_pattern not in improved_pattern:
                    improved_pattern = improved_pattern.replace(
                        node_pattern,
                        capture_pattern,
                        1  # Replace only one to avoid overfitting
                    )
                    # Increase confidence
                    confidence += 0.05
        
        return {
            "pattern": improved_pattern,
            "confidence": min(confidence, 0.95)  # Cap at 0.95
        }

class PredicateRefinement(BaseLearningStrategy):
    """Refines predicates in the pattern based on insights."""
    
    def __init__(self):
        """Initialize predicate refinement strategy."""
        super().__init__(name="predicate_refinement")
    
    async def _apply_strategy(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Refine predicates in the pattern based on insights.
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Insights collected for the pattern
            language_id: Language ID
            
        Returns:
            Dictionary with improved pattern and confidence if improved
        """
        if not insights.get("predicates_success"):
            return None
        
        # Find predicates with poor success rates
        poor_predicates = [
            pred for pred, stats in insights["predicates_success"].items()
            if stats["success"] / (stats["success"] + stats["failure"]) < 0.3  # Less than 30% success
            if stats["success"] + stats["failure"] > 5  # At least 5 occurrences
        ]
        
        if not poor_predicates:
            return None
        
        improved_pattern = pattern
        confidence = insights.get("pattern_confidence", 0.5)
        
        # Remove or adjust poor predicates
        for predicate in poor_predicates:
            # Extract capture name from predicate
            match = re.search(r"#\w+\?\s+@(\w+)", predicate)
            if match:
                capture_name = match.group(1)
                
                # Try to adjust predicate or remove it
                if "#match?" in predicate:
                    # Make match pattern more permissive
                    current_pattern = re.search(r'"([^"]+)"', predicate)
                    if current_pattern:
                        original = current_pattern.group(1)
                        relaxed = original.replace("^", "").replace("$", "")
                        improved_pattern = improved_pattern.replace(
                            predicate,
                            predicate.replace(original, relaxed),
                            1
                        )
                elif "#eq?" in predicate:
                    # Remove equality check
                    improved_pattern = improved_pattern.replace(
                        predicate,
                        "",
                        1
                    )
                else:
                    # Just remove the predicate
                    improved_pattern = improved_pattern.replace(
                        predicate,
                        "",
                        1
                    )
            
            # Slight confidence reduction since we're making pattern more general
            confidence -= 0.03
        
        return {
            "pattern": improved_pattern,
            "confidence": max(confidence, 0.3)  # Don't go below 0.3
        }

class PatternGeneralization(BaseLearningStrategy):
    """Generalizes the pattern for better cross-project applicability."""
    
    def __init__(self):
        """Initialize pattern generalization strategy."""
        super().__init__(name="pattern_generalization")
    
    async def _apply_strategy(
        self, 
        pattern: str, 
        insights: Dict[str, Any], 
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generalize the pattern for better cross-project applicability.
        
        Args:
            pattern: Tree-sitter pattern to improve
            insights: Insights collected for the pattern
            language_id: Language ID
            
        Returns:
            Dictionary with improved pattern and confidence if improved
        """
        # Check if we have enough data to generalize
        if len(insights.get("matches", [])) < 5:
            return None
        
        improved_pattern = pattern
        confidence = insights.get("pattern_confidence", 0.5)
        
        # 1. Replace hard-coded strings with wildcards
        string_literals = re.findall(r'"([^"]+)"', pattern)
        
        for literal in string_literals:
            # Don't replace regex patterns in predicates
            if (
                "^" in literal or 
                "$" in literal or 
                "*" in literal or 
                "+" in literal or
                "?" in literal
            ):
                continue
                
            # Replace with more permissive match
            if len(literal) > 3:  # Only generalize longer strings
                improved_pattern = improved_pattern.replace(
                    f'"{literal}"',
                    f'".*"',
                    1
                )
                # Reduce confidence slightly
                confidence -= 0.02
        
        # 2. Make strict parent-child relationships optional where appropriate
        for relation in [
            ("parent", "child"),
            ("class", "method"),
            ("function", "parameter"),
            ("if", "then"),
            ("for", "body")
        ]:
            parent, child = relation
            if f"({parent}" in improved_pattern and f"({child}" in improved_pattern:
                # Add optional marker to child if not already present
                child_pattern = re.search(r"\(" + child + r"[^\)]*\)", improved_pattern)
                if child_pattern:
                    child_match = child_pattern.group(0)
                    if not child_match.endswith("?"):
                        improved_pattern = improved_pattern.replace(
                            child_match,
                            child_match + "?",
                            1
                        )
                        # Slight confidence adjustment
                        confidence -= 0.01
        
        # Only return if we made changes
        if improved_pattern != pattern:
            return {
                "pattern": improved_pattern,
                "confidence": max(confidence, 0.3)  # Don't go below 0.3
            }
        
        return None

# Define available strategies
def get_learning_strategies() -> Dict[str, BaseLearningStrategy]:
    """Get all available learning strategies.
    
    Returns:
        Dictionary of learning strategies
    """
    return {
        "node_pattern_improvement": NodePatternImprovement(),
        "capture_optimization": CaptureOptimization(),
        "predicate_refinement": PredicateRefinement(),
        "pattern_generalization": PatternGeneralization()
    } 