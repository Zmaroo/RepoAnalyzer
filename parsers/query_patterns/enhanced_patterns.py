"""Enhanced tree-sitter pattern functionality for RepoAnalyzer.

This module provides advanced pattern capabilities that enhance the existing
query patterns with features like context awareness, learning, and error recovery.
Specialized for tree-sitter parsers with tree-based pattern matching.
"""

from typing import Dict, Any, List, Optional, Set, TypeVar, Generic, Union, Callable, Tuple
from dataclasses import dataclass, field, asdict
import asyncio
import time
import copy
from collections import defaultdict
import os
import json
import re

# Import base pattern classes
from parsers.query_patterns.base_patterns import (
    BasePatternContext, BasePatternPerformanceMetrics, BasePattern,
    BaseAdaptivePattern, BaseResilientPattern, BaseCrossProjectPatternLearner
)

# Import feature extractor base classes from the correct modules
from parsers.feature_extractor import FeatureExtractor, TreeSitterFeatureExtractor

# Core parser components
from parsers.types import (
    QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, FileType, ParserType, PatternValidationResult,
    ExtractedFeatures, BlockType, AICapability
)
from parsers.base_parser import BaseParser
from parsers.block_extractor import BlockExtractor, ExtractedBlock
from utils.logger import log
from utils.cache import UnifiedCache
from utils.health_monitor import global_health_monitor, ComponentStatus
from parsers.tree_sitter_parser import get_parser as get_ts_parser

# Import utility modules
from parsers.query_patterns.tree_sitter_utils import (
    count_nodes, execute_tree_sitter_query, extract_captures, regex_matches
)
from parsers.query_patterns.learning_strategies import get_learning_strategies
from parsers.query_patterns.recovery_strategies import get_recovery_strategies

# Import common pattern functionality
from parsers.query_patterns.common import (
    process_tree_sitter_pattern, validate_tree_sitter_pattern, 
    create_tree_sitter_context, update_common_pattern_metrics,
    TreeSitterPatternLearner  # Base class for TreeSitterCrossProjectPatternLearner
)

# Tree-sitter support
try:
    from tree_sitter import Parser, Language, Query
    TREE_SITTER_AVAILABLE = True
except ImportError:
    # Fallback for when tree-sitter is not available
    get_binding = get_language = get_parser = lambda *args, **kwargs: None
    SupportedLanguage = None
    TREE_SITTER_AVAILABLE = False

# Utilities
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor, ComponentStatus
from db.transaction import transaction_scope

# Define DATA_DIR for pattern insights storage
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

@dataclass
class TreeSitterPatternContext(BasePatternContext):
    """Context information for tree-sitter pattern matching.
    
    This class provides context for pattern matching operations,
    specialized for tree-sitter parsing approaches.
    """
    # Override parser_type to default to tree-sitter
    parser_type: ParserType = ParserType.TREE_SITTER
    
    # Tree-sitter specific context fields
    ast_node: Optional[Dict[str, Any]] = None
    query_captures: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    node_types: Set[str] = field(default_factory=set)
    capture_names: Set[str] = field(default_factory=set)
    syntax_errors: List[Dict[str, Any]] = field(default_factory=list)
    last_query_time: float = 0.0
    
    def get_parser_specific_context(self) -> Dict[str, Any]:
        """Get parser-specific context information."""
        return {
            "ast": self.code_structure,
            "language_id": self.language_id,
            "tree_sitter_available": True,
            "capture_points": self.metadata.get("capture_points", {}),
            "query_context": self.metadata.get("query_context", {}),
            "node_types": list(self.node_types),
            "capture_names": list(self.capture_names),
            "has_syntax_errors": bool(self.syntax_errors)
        }

class TreeSitterPatternPerformanceMetrics(BasePatternPerformanceMetrics):
    """Tree-sitter specific pattern performance metrics.
    
    Extends the base metrics with tree-sitter specific performance tracking.
    """
    
    def __init__(self):
        """Initialize pattern performance metrics."""
        super().__init__()
        
        # Tree-sitter specific metrics
        self.query_compilation_time: List[float] = []
        self.node_count: List[int] = []
        self.capture_count: List[int] = []
        self.exceeded_match_limit = 0
        self.exceeded_time_limit = 0
        
    def update_tree_sitter_metrics(
        self,
        query_time: float,
        node_count: int,
        capture_count: int,
        exceeded_match_limit: bool = False,
        exceeded_time_limit: bool = False
    ):
        """Update tree-sitter specific metrics.
        
        Args:
            query_time: Time to compile and run query
            node_count: Number of nodes in the AST
            capture_count: Number of captures in the result
            exceeded_match_limit: Whether match limit was exceeded
            exceeded_time_limit: Whether time limit was exceeded
        """
        self.query_compilation_time.append(query_time)
        self.node_count.append(node_count)
        self.capture_count.append(capture_count)
        
        if exceeded_match_limit:
            self.exceeded_match_limit += 1
        
        if exceeded_time_limit:
            self.exceeded_time_limit += 1
    
    def get_avg_query_time(self) -> float:
        """Get average query compilation time."""
        return sum(self.query_compilation_time) / len(self.query_compilation_time) if self.query_compilation_time else 0.0
    
    def get_avg_node_count(self) -> int:
        """Get average node count."""
        return int(sum(self.node_count) / len(self.node_count)) if self.node_count else 0
    
    def get_avg_capture_count(self) -> int:
        """Get average capture count."""
        return int(sum(self.capture_count) / len(self.capture_count)) if self.capture_count else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a serializable dictionary."""
        base_dict = super().to_dict()
        tree_sitter_dict = {
            "avg_query_time": self.get_avg_query_time(),
            "avg_node_count": self.get_avg_node_count(),
            "avg_capture_count": self.get_avg_capture_count(),
            "exceeded_match_limit": self.exceeded_match_limit,
            "exceeded_time_limit": self.exceeded_time_limit
        }
        return {**base_dict, **tree_sitter_dict}

class TreeSitterPattern(BasePattern):
    """Base tree-sitter query pattern implementation.
    
    This class provides fundamental tree-sitter query pattern functionality for RepoAnalyzer,
    implementing core pattern matching capabilities using tree-sitter queries.
    """
    
    def __init__(
        self, 
        name: str,
        pattern: str,
        category: PatternCategory = PatternCategory.CODE_PATTERNS,
        purpose: PatternPurpose = PatternPurpose.UNDERSTANDING,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None
    ):
        """Initialize tree-sitter pattern.
        
        Args:
            name: Name of the pattern
            pattern: Tree-sitter query pattern string
            category: Pattern category
            purpose: Pattern purpose
            language_id: Language identifier
            confidence: Confidence level
            metadata: Additional metadata
            extract: Function to extract structured data from matches
            test_cases: Test cases for pattern validation
        """
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata or {},
            extract=extract,
            test_cases=test_cases or []
        )
        
        # Tree-sitter specific components
        self._tree_sitter_parser = None
        self._query = None
        
        # Performance metrics
        self.metrics = TreeSitterPatternPerformanceMetrics()
        
        # Cache for efficiency
        self._pattern_cache = UnifiedCache(
            f"tree_sitter_pattern_{name}_cache",
            eviction_policy="lru", 
            max_size=500
        )
    
    async def initialize(self):
        """Initialize required components."""
        await super().initialize()
        
        if not self._tree_sitter_parser:
            self._tree_sitter_parser = await get_ts_parser(self.language_id)
            
        # Try to compile the query
        if self._tree_sitter_parser and self.pattern:
            try:
                self._query = self._tree_sitter_parser.compile_query(self.pattern)
            except Exception as e:
                await log(
                    f"Error compiling query for {self.name}: {e}",
                    level="error",
                    context={
                        "pattern_name": self.name,
                        "language_id": self.language_id,
                        "pattern": self.pattern[:100] + "..." if len(self.pattern) > 100 else self.pattern
                    }
                )
    
    async def matches(
        self,
        source_code: str,
        context: Optional[TreeSitterPatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Get matches from tree-sitter query.
        
        Args:
            source_code: Source code to match against
            context: Optional context information
            
        Returns:
            List of matches with extracted information
        """
        await self.initialize()
        start_time = time.time()
        context_key = context.get_context_key() if context else None
        
        try:
            # Try cache first
            cache_key = f"{hash(source_code)}:{context_key or ''}:{self.name}"
            cached_result = await self._pattern_cache.get(cache_key)
            if cached_result:
                self.metrics.update(
                    success=bool(cached_result),
                    execution_time=0.001,  # Negligible time for cache hit
                    context_key=context_key,
                    parser_type=ParserType.TREE_SITTER,
                    pattern_name=self.name,
                    cache_hit=True
                )
                return cached_result
            
            # Determine if we should use the common pattern processing
            use_common_processor = self.purpose == PatternPurpose.UNDERSTANDING
            
            matches = []
            if use_common_processor:
                # Import the process_tree_sitter_pattern function
                from parsers.query_patterns.common import process_tree_sitter_pattern
                # Use the tree-sitter pattern processor
                matches = await process_tree_sitter_pattern(self, source_code, context)
            else:
                # Execute tree-sitter query directly
                matches = await self._execute_query(source_code)
            
            # Update metrics
            execution_time = time.time() - start_time
            self.metrics.update(
                success=bool(matches),
                execution_time=execution_time,
                context_key=context_key,
                parser_type=ParserType.TREE_SITTER,
                pattern_name=self.name,
                cache_hit=False
            )
            
            # Cache result
            await self._pattern_cache.set(cache_key, matches)
            
            return matches
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics.update(
                success=False,
                execution_time=execution_time,
                context_key=context_key,
                parser_type=ParserType.TREE_SITTER,
                pattern_name=self.name
            )
            await log(
                f"Error in tree-sitter pattern matching: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "parser_type": ParserType.TREE_SITTER.value
                }
            )
            return []
    
    async def _execute_query(self, source_code: str) -> List[Dict[str, Any]]:
        """Execute tree-sitter query.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches with extracted information
        """
        await self.initialize()
        
        if not self._tree_sitter_parser or not self._query:
            return []
        
        try:
            matches, metrics = await execute_tree_sitter_query(
                source_code,
                self._tree_sitter_parser,
                self._query,
                timeout_micros=5000,  # 5ms timeout
                extract_fn=self.extract,
                pattern_name=self.name
            )
            
            # Update performance metrics
            if metrics:
                self.metrics.update_tree_sitter_metrics(
                    query_time=metrics.get("query_time", 0),
                    node_count=metrics.get("node_count", 0),
                    capture_count=metrics.get("capture_count", 0),
                    exceeded_match_limit=metrics.get("exceeded_match_limit", False),
                    exceeded_time_limit=metrics.get("exceeded_time_limit", False)
                )
                
                # Update common pattern metrics
                from parsers.query_patterns.common import update_common_pattern_metrics
                await update_common_pattern_metrics(
                    self.name,
                    {
                        "execution_time": metrics.get("query_time", 0),
                        "matches": len(matches),
                        "parser_type": "tree_sitter"
                    }
                )
            
            return matches
            
        except Exception as e:
            await log(
                f"Error in tree-sitter query execution: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id
                }
            )
            return []
    
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate pattern against source code.
        
        Delegates to the system's validation infrastructure.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: Validation result
        """
        try:
            # Import the validate_tree_sitter_pattern function from common
            from parsers.query_patterns.common import validate_tree_sitter_pattern
            
            # Create a tree-sitter specific context
            from parsers.types import AIContext
            
            context = AIContext(
                language_id=self.language_id,
                pattern_metadata=self.metadata,
                parser_type=ParserType.TREE_SITTER
            )
            
            # Use the tree-sitter validation infrastructure
            return await validate_tree_sitter_pattern(self, context)
            
        except Exception as e:
            await log(
                f"Error validating pattern: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "error_type": type(e).__name__
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
    
    async def test(self, source_code: str) -> Dict[str, Any]:
        """Test pattern against source code.
        
        Uses the pattern processor's test_pattern method for detailed results.
        
        Args:
            source_code: The source code to test
            
        Returns:
            Dict[str, Any]: Test results with detailed metrics
        """
        try:
            # Use pattern processor for testing
            from parsers.pattern_processor import get_pattern_processor
            
            processor = await get_pattern_processor(self.language_id)
            if not processor:
                return {
                    "success": False,
                    "errors": ["Pattern processor not available"]
                }
            
            # Execute the test with explicit tree-sitter flag
            return await processor.test_pattern(
                self.name, 
                source_code, 
                is_tree_sitter=True
            )
        except Exception as e:
            await log(
                f"Error testing pattern: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "error_type": type(e).__name__
                }
            )
            return {
                "success": False,
                "errors": [f"Test error: {str(e)}"]
            }
    
    async def validate_syntax(self) -> Dict[str, Any]:
        """Validate the syntax of the tree-sitter query.
        
        Uses tree-sitter parser's analyze_query method.
            
        Returns:
            Dict[str, Any]: Validation results including captures and complexity
        """
        try:
            # Use tree-sitter parser directly for query analysis
            from parsers.tree_sitter_parser import get_tree_sitter_parser
            
            parser = await get_tree_sitter_parser(self.language_id)
            if not parser:
                return {
                    "valid": False,
                    "errors": ["Tree-sitter parser not available"]
                }
            
            # Analyze query structure
            return parser.analyze_query(self.pattern)
        except Exception as e:
            await log(
                f"Error validating syntax: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "error_type": type(e).__name__
                }
            )
            return {
                "valid": False,
                "errors": [f"Syntax validation error: {str(e)}"]
            }
    
    async def validate_against_test_cases(self) -> Dict[str, Any]:
        """Validate pattern against its test cases.
        
        Returns:
            Dict[str, Any]: Validation results for each test case
        """
        results = {}
        
        if not self.test_cases:
            return {"valid": False, "error": "No test cases defined"}
        
        from parsers.pattern_processor import get_pattern_processor
        processor = await get_pattern_processor(self.language_id)
        if not processor:
            return {"valid": False, "error": "Pattern processor not available"}
        
        for i, test_case in enumerate(self.test_cases):
            if "code" not in test_case:
                results[f"test_{i}"] = {"valid": False, "error": "No code in test case"}
                continue
                
            # Test against this specific test case
            test_result = await processor.test_pattern(
                self.name,
                test_case["code"],
                is_tree_sitter=True
            )
            
            # Check if the expected result matches
            expected_valid = test_case.get("should_match", True)
            actual_valid = test_result.get("success", False)
            
            results[f"test_{i}"] = {
                "valid": expected_valid == actual_valid,
                "expected": expected_valid,
                "actual": actual_valid,
                "details": test_result
            }
        
        # Overall validity
        overall_valid = all(r.get("valid", False) for r in results.values())
        
        return {
            "valid": overall_valid,
            "test_cases": results
        }

class TreeSitterAdaptivePattern(BaseAdaptivePattern):
    """Adaptive tree-sitter pattern with context-aware capabilities.
    
    This pattern type can adapt to different contexts, improving its
    matching capabilities based on the code structure it encounters.
    """
    
    def __init__(
        self,
        name: str,
        pattern: str,
        category: PatternCategory,
        purpose: PatternPurpose,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        regex_pattern: Optional[str] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        query_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize an adaptive tree-sitter pattern.
        
        Args:
            name: Pattern name
            pattern: Tree-sitter query pattern
            category: Pattern category
            purpose: Pattern purpose
            language_id: Language ID
            confidence: Confidence score (0.0-1.0)
            metadata: Additional metadata
            extract: Function to extract structured data from matches
            regex_pattern: Optional regex fallback pattern
            test_cases: Test cases for pattern validation
            query_config: Configuration for query execution
        """
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata or {},
            extract=extract,
            test_cases=test_cases or []
        )
        
        # Store regex pattern for fallback
        self.regex_pattern = regex_pattern
        
        # Configuration for tree-sitter query execution
        self.query_config = query_config or {
            "timeout_micros": 5000,  # 5ms timeout
            "match_limit": 100,      # Prevent excessive processing
            "byte_range": None       # Optional range limit
        }
        
        # Pattern performance metrics
        self.metrics = TreeSitterPatternPerformanceMetrics()
        
        # Caching support
        self._pattern_cache = UnifiedCache(
            f"tree_sitter_pattern_{name}_cache", 
            eviction_policy="lru", 
            max_size=1000
        )
        
        # Required components
        self._block_extractor = None
        self._base_parser = None
        self._tree_sitter_parser = None
        self._query = None
    
    async def validate_and_adapt(self, source_code: str) -> PatternValidationResult:
        """Validate pattern and adapt to context if needed.
        
        This enhanced validation method will automatically adapt the pattern
        if validation fails, attempting to improve its matching capabilities.
        
        Args:
            source_code: Source code to validate against
            
        Returns:
            PatternValidationResult indicating validation status
        """
        try:
            # First try standard validation
            from parsers.query_patterns.common import validate_tree_sitter_pattern
            
            validation_result = await validate_tree_sitter_pattern(self)
            
            if validation_result.is_valid:
                return validation_result
                
            # Validation failed, try to adapt pattern
            async with pattern_processor() as processor:
                # Create context from source code
                context = await create_tree_sitter_context(
                    "",  # No file path for direct source code
                    processor.parse(source_code, self.language_id).ast,
                    parser_type=ParserType.TREE_SITTER
                )
                
                # Adapt pattern to context
                await self.adapt_to_context(context)
                
                # Try validating again
                validation_result = await validate_tree_sitter_pattern(self)
                
                # Add adaptation metadata
                if validation_result.metadata is None:
                    validation_result.metadata = {}
                    
                validation_result.metadata["adapted"] = True
                validation_result.metadata["original_pattern"] = self.pattern
                
                return validation_result
                
        except Exception as e:
            await log(
                f"Error validating and adapting pattern: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "error_type": type(e).__name__
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
    
    async def initialize(self):
        """Initialize the pattern and compile query."""
        await super().initialize()
        
        # Initialize tree-sitter parser
        self._tree_sitter_parser = await get_ts_parser(self.language_id)
        
        # Compile tree-sitter query
        if self._tree_sitter_parser and self.pattern:
            try:
                self._query = self._tree_sitter_parser.compile_query(self.pattern)
            except Exception as e:
                await log(
                    f"Error compiling query for {self.name}: {e}",
                    level="error",
                    context={"pattern_name": self.name}
                )
    
    async def matches(self, source_code: str, context: Optional[TreeSitterPatternContext] = None) -> List[Dict[str, Any]]:
        """Match pattern against source code with adaptive capabilities."""
        # Initialize if needed
        if not self._tree_sitter_parser or not self._query:
            await self.initialize()
            
        # Create context if not provided
        if not context:
            context = TreeSitterPatternContext(
                language_id=self.language_id,
                file_path="<memory>",
                file_type=FileType.CODE
            )
            
            # Parse source code to populate context
            if self._tree_sitter_parser:
                tree = self._tree_sitter_parser.parse(source_code)
                if tree and tree.root_node:
                    context.code_structure = {
                        "ast": tree.root_node,
                        "language_id": self.language_id
                    }
        
        # Try to match with current pattern
        matches = await self._tree_sitter_matches(source_code)
        
        # If no matches and adaptation is enabled, try to adapt
        if not matches and self.metadata.get("enable_adaptation", True):
            # Store original pattern
            original_pattern = self.pattern
            
            # Adapt pattern to context
            await self.adapt_to_context(context)
            
            # If pattern was adapted, try matching again
            if self.pattern != original_pattern:
                try:
                    # Recompile query with adapted pattern
                    if self._tree_sitter_parser:
                        self._query = self._tree_sitter_parser.compile_query(self.pattern)
                        
                        # Try matching with adapted pattern
                        matches = await self._tree_sitter_matches(source_code)
                        
                        # If still no matches, revert to original pattern
                        if not matches:
                            self.pattern = original_pattern
                            self._query = self._tree_sitter_parser.compile_query(self.pattern)
                except Exception as e:
                    # If compilation fails, revert to original pattern
                    self.pattern = original_pattern
                    await log(
                        f"Adapted pattern compilation failed: {e}",
                        level="warning",
                        context={"pattern_name": self.name}
                    )
        
        # If still no matches and regex fallback is available, try it
        if not matches and self.regex_pattern:
            matches = await self._regex_matches(source_code)
        
        return matches
    
    async def _tree_sitter_query(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Execute tree-sitter query against source code.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            Query result or None if failed
        """
        if not self._tree_sitter_parser or not self.pattern:
            return None
            
        try:
            # Compile query if needed
            if not self._query:
                self._query = self._tree_sitter_parser.compile_query(self.pattern)
                
            return self._query
        except Exception as e:
            await log(
                f"Error in tree-sitter query: {e}",
                level="warning",
                context={"pattern_name": self.name}
            )
            return None
    
    async def _tree_sitter_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Get matches using tree-sitter query.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches
        """
        if not self._tree_sitter_parser or not self._query:
            await self.initialize()
            if not self._tree_sitter_parser or not self._query:
                return []
                
        try:
            # Use the utility function from tree_sitter_utils
            matches, metrics = await execute_tree_sitter_query(
                source_code,
                self._tree_sitter_parser,
                self._query,
                timeout_micros=self.query_config.get("timeout_micros", 5000),
                match_limit=self.query_config.get("match_limit", 100),
                extract_fn=self.extract,
                pattern_name=self.name
            )
            
            # Update tree-sitter specific metrics
            if isinstance(self.metrics, TreeSitterPatternPerformanceMetrics) and metrics:
                self.metrics.update_tree_sitter_metrics(
                    query_time=metrics.get("query_time", 0),
                    node_count=metrics.get("node_count", 0),
                    capture_count=metrics.get("capture_count", 0),
                    exceeded_match_limit=metrics.get("exceeded_match_limit", False),
                    exceeded_time_limit=metrics.get("exceeded_time_limit", False)
                )
                
                return matches
            
        except Exception as e:
            await log(
                f"Error in tree-sitter matching: {e}",
                level="warning",
                context={"pattern_name": self.name}
            )
        return []
    
    async def _regex_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Match using regex pattern.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches
        """
        if not self.regex_pattern:
            return []
            
        # Use the utility function from tree_sitter_utils
        return await regex_matches(
            source_code,
            self.regex_pattern,
            extract_fn=self.extract,
            pattern_name=self.name
        )
    
    async def adapt_to_context(self, context: TreeSitterPatternContext) -> None:
        """Adapt pattern to context.
        
        This method analyzes the context and adapts the pattern to better
        match the code structure.
        
        Args:
            context: Context to adapt to
        """
        if not context or not context.code_structure:
            return
            
        # Adapt tree-sitter pattern
        await self._adapt_tree_sitter_pattern(context)
        
        # Adapt regex pattern if available
        if self.regex_pattern:
            await self._adapt_regex_pattern(context)
    
    async def _adapt_tree_sitter_pattern(self, context: TreeSitterPatternContext) -> None:
        """Adapt tree-sitter pattern to context.
        
        Args:
            context: Context to adapt to
        """
        # This is a simplified implementation
        # In a real implementation, this would analyze the AST and make
        # more sophisticated adaptations based on the code structure
        
        # Example: Make optional nodes mandatory if they appear frequently
        if "?" in self.pattern:
            ast = context.code_structure.get("ast")
            if ast:
                # Check if optional nodes are present in the AST
                # This is a placeholder for more sophisticated analysis
                node_count = await count_nodes(ast)
                if node_count > 100:  # Complex AST
                    # Make some optional nodes mandatory for complex code
                    self.pattern = self.pattern.replace(")?", ")")
    
    async def _adapt_regex_pattern(self, context: TreeSitterPatternContext) -> None:
        """Adapt regex pattern to context.
        
        Args:
            context: Context to adapt to
        """
        # This is a simplified implementation
        # In a real implementation, this would analyze the code structure
        # and adapt the regex pattern accordingly
        
        # Example: Adjust whitespace handling based on code style
        if self.regex_pattern and context.metadata.get("code_style"):
            code_style = context.metadata["code_style"]
            if code_style.get("uses_tabs", False):
                # Adjust regex to handle tabs
                self.regex_pattern = self.regex_pattern.replace(r"\s+", r"[ \t]+")
            elif code_style.get("indent_size"):
                # Adjust regex to handle specific indentation
                indent_size = code_style["indent_size"]
                self.regex_pattern = self.regex_pattern.replace(
                    r"^\s+", 
                    f"^\\s{{{indent_size}}}"
                )

class TreeSitterResilientPattern(BaseResilientPattern):
    """Resilient tree-sitter pattern with error recovery capabilities.
    
    This pattern type includes fallback mechanisms and error recovery
    strategies to handle parsing errors and pattern matching failures.
    """
    
    def __init__(
        self, 
        name: str,
        pattern: str,
        category: PatternCategory = PatternCategory.CODE_PATTERNS,
        purpose: PatternPurpose = PatternPurpose.UNDERSTANDING,
        language_id: str = "*",
        confidence: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
        extract: Optional[Callable] = None,
        regex_pattern: Optional[str] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        fallback_patterns: Optional[List[str]] = None,
        recovery_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize tree-sitter resilient pattern.
        
        Args:
            name: Pattern name
            pattern: Tree-sitter query pattern
            category: Pattern category
            purpose: Pattern purpose
            language_id: Language ID
            confidence: Confidence score (0.0-1.0)
            metadata: Additional metadata
            extract: Function to extract structured data from matches
            regex_pattern: Optional regex fallback pattern
            test_cases: Test cases for pattern validation
            fallback_patterns: List of fallback patterns to try if main pattern fails
            recovery_config: Configuration for recovery strategies
        """
        super().__init__(
            name=name,
            pattern=pattern,
            category=category,
            purpose=purpose,
            language_id=language_id,
            confidence=confidence,
            metadata=metadata or {},
            extract=extract,
            test_cases=test_cases or []
        )
        
        # Store these as attributes if needed for recovery logic
        self.fallback_patterns = fallback_patterns or []
        self.recovery_config = recovery_config or {
            "strategies": ["fallback_patterns", "regex_fallback", "partial_match"],
            "max_attempts": 3,
            "timeout": 5.0
        }
        
        # Recovery metrics
        self.recovery_metrics = {
            "attempts": 0,
            "successes": 0,
            "avg_recovery_time": 0.0,
            "strategy_stats": {}
        }
        
        # Recovery strategies
        self._recovery_strategies = get_recovery_strategies()
        
        # Required components
        self._tree_sitter_parser = None
        self._query = None
    
    async def validate_with_recovery(self, source_code: str) -> PatternValidationResult:
        """Validate pattern with recovery options if validation fails."""
        try:
            # First try standard validation
            from parsers.query_patterns.common import validate_tree_sitter_pattern
            
            validation_result = await validate_tree_sitter_pattern(self)
            
            if validation_result.is_valid:
                return validation_result
            
            # Validation failed, try recovery strategies
            recovery_result = await self._try_recovery_strategies(
                source_code, 
                validation_result.errors
            )
            
            # Update metrics if we have them
            if hasattr(self, 'recovery_strategies') and self.recovery_strategies:
                for strategy_name, strategy in self.recovery_strategies.items():
                    if hasattr(strategy, 'metrics'):
                        if not validation_result.metadata:
                            validation_result.metadata = {}
                        
                        if "recovery_metrics" not in validation_result.metadata:
                            validation_result.metadata["recovery_metrics"] = {}
                        
                        validation_result.metadata["recovery_metrics"][strategy_name] = strategy.metrics
            
            return recovery_result
            
        except Exception as e:
            await log(
                f"Error in resilient validation: {e}",
                level="error",
                context={
                    "pattern_name": self.name,
                    "language_id": self.language_id,
                    "error_type": type(e).__name__
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[f"Resilient validation error: {str(e)}"]
            )
    
    async def _try_recovery_strategies(
        self,
        source_code: str,
        original_errors: List[str]
    ) -> PatternValidationResult:
        """Try recovery strategies to find matches."""
        # Track recovery attempt
        self.recovery_metrics["attempts"] += 1
        start_time = time.time()
        
        # Get enabled strategies
        enabled_strategies = self.recovery_config.get("strategies", [])
        
        # Try each strategy in order
        for strategy_name in enabled_strategies:
            if strategy_name not in self._recovery_strategies:
                continue
            
            strategy = self._recovery_strategies[strategy_name]
            
            # Prepare strategy-specific arguments
            kwargs = {
                "tree_sitter_parser": self._tree_sitter_parser,
                "query": self._query,
                "extract_fn": self.extract,
                "fallback_patterns": self.fallback_patterns,
                "regex_pattern": self.regex_pattern
            }
            
            # Apply the strategy
            result = await strategy.apply(source_code, self.name, **kwargs)
            
            # Update strategy stats
            if strategy_name not in self.recovery_metrics["strategy_stats"]:
                self.recovery_metrics["strategy_stats"][strategy_name] = {
                    "attempts": 0,
                    "successes": 0
                }
            
            self.recovery_metrics["strategy_stats"][strategy_name]["attempts"] += 1
            
            # If strategy succeeded, return matches
            if result.get("success", False) and result.get("matches"):
                # Update success metrics
                self.recovery_metrics["successes"] += 1
                self.recovery_metrics["strategy_stats"][strategy_name]["successes"] += 1
                
                # Update average recovery time
                recovery_time = time.time() - start_time
                total_successes = self.recovery_metrics["successes"]
                prev_avg = self.recovery_metrics["avg_recovery_time"]
                self.recovery_metrics["avg_recovery_time"] = (
                    (prev_avg * (total_successes - 1) + recovery_time) / total_successes
                    if total_successes > 0 else recovery_time
                )
                
                return PatternValidationResult(
                    is_valid=True,
                    matches=result.get("matches", []),
                    metadata={
                        "strategy": strategy_name,
                        "recovery_time": recovery_time,
                        "fallback_index": result.get("fallback_index"),
                        "partial_match": result.get("partial_match", False)
                    }
                )
        
        # If all strategies failed, return invalid result
        return PatternValidationResult(
            is_valid=False,
            errors=original_errors + ["All recovery strategies failed"]
        )
    
    async def initialize(self):
        """Initialize the pattern and compile queries."""
        await super().initialize()
        await self.compile_query()
        await self.compile_fallbacks()
    
    async def compile_query(self):
        """Compile the tree-sitter query."""
        self._tree_sitter_parser = await get_ts_parser(self.language_id)
        if self._tree_sitter_parser and self.pattern:
            try:
                self._query = self._tree_sitter_parser.compile_query(self.pattern)
            except Exception as e:
                await log(f"Error compiling query for {self.name}: {e}", level="error")
    
    async def compile_fallbacks(self):
        """Compile fallback patterns."""
        if self._tree_sitter_parser:
            self.fallback_queries = []
            for fallback in self.fallback_patterns:
                try:
                    query = self._tree_sitter_parser.compile_query(fallback)
                    self.fallback_queries.append(query)
                except Exception as e:
                    await log(f"Error compiling fallback for {self.name}: {e}", level="warning")
    
    async def matches(
        self, 
        source_code: str,
        context: Optional[TreeSitterPatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Match pattern against source code with fallback mechanisms.
        
        This method attempts to match the primary pattern first, and if it fails,
        it will try fallback patterns and recovery strategies.
        
        Args:
            source_code: Source code to match against
            context: Optional context for matching
            
        Returns:
            List of matches
        """
        # Initialize if needed
        if not self._tree_sitter_parser or not self._query:
            await self.initialize()
            
        # Try primary pattern first
        primary_matches = await self._execute_tree_sitter_query(source_code, self._query)
        
        # If primary pattern matched, return results
        if primary_matches:
            return primary_matches
            
        # Try fallback patterns
        for idx, fallback_query in enumerate(self.fallback_queries):
            fallback_matches = await self._execute_tree_sitter_query(
                source_code, 
                fallback_query,
                is_fallback=True,
                fallback_index=idx
            )
            
            if fallback_matches:
                return fallback_matches
                
        # Try regex fallback if available
        if self.regex_pattern:
            regex_matches = await self._regex_matches(source_code)
            if regex_matches:
                return regex_matches
                
        # Try partial matching as last resort
        if "partial_match" in self.recovery_config.get("strategies", []):
            partial_matches = await self._try_partial_matches(source_code)
            if partial_matches:
                return partial_matches
                
        # No matches found
        return []
    
    async def _execute_tree_sitter_query(
        self, 
        source_code: str,
        query: Optional[Any],
        is_fallback: bool = False,
        fallback_index: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Execute a tree-sitter query against source code."""
        if not query or not self._tree_sitter_parser:
            return []
            
        try:
            # Execute query
            matches, _ = await execute_tree_sitter_query(
                source_code,
                self._tree_sitter_parser,
                query,
                extract_fn=self.extract,
                is_fallback=is_fallback,
                fallback_index=fallback_index,
                pattern_name=self.name
            )
            
            return matches
            
        except Exception as e:
            await log(
                f"Error in tree-sitter query execution: {e}",
                level="warning" if is_fallback else "error",
                context={
                    "pattern_name": self.name,
                    "is_fallback": is_fallback,
                    "fallback_index": fallback_index
                }
            )
            return []
    
    async def _regex_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Match using regex pattern.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches
        """
        if not self.regex_pattern:
            return []
            
        # Use the utility function from tree_sitter_utils
        return await regex_matches(
            source_code,
            self.regex_pattern,
            extract_fn=self.extract,
            pattern_name=self.name
        )
    
    async def _try_partial_matches(self, source_code: str) -> List[Dict[str, Any]]:
        """Try to match on segments of source code.
        
        This is a fallback mechanism that tries to match the pattern
        on smaller segments of the source code.
        
        Args:
            source_code: Source code to match against
            
        Returns:
            List of matches
        """
        if not self._query or not self._tree_sitter_parser:
            return []
            
        try:
            # Use the partial match strategy directly
            strategy = self._recovery_strategies.get("partial_match")
            if not strategy:
                return []
                
            result = await strategy.apply(
                source_code,
                self.name,
                tree_sitter_parser=self._tree_sitter_parser,
                query=self._query,
                extract_fn=self.extract
            )
            
            if result.get("success", False):
                return result.get("matches", [])
                
            return []
            
        except Exception as e:
            await log(
                f"Error in partial matching: {e}",
                level="warning",
                context={"pattern_name": self.name}
            )
            return []
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics.
        
        Returns:
            Dictionary with recovery statistics
        """
        stats = {
            "attempts": self.recovery_metrics["attempts"],
            "successes": self.recovery_metrics["successes"],
            "success_rate": (
                self.recovery_metrics["successes"] / self.recovery_metrics["attempts"]
                if self.recovery_metrics["attempts"] > 0 else 0.0
            ),
            "avg_recovery_time": self.recovery_metrics["avg_recovery_time"],
            "strategies": {}
        }
        
        # Add strategy-specific stats
        for strategy_name, strategy_stats in self.recovery_metrics["strategy_stats"].items():
            stats["strategies"][strategy_name] = {
                "attempts": strategy_stats["attempts"],
                "successes": strategy_stats["successes"],
                "success_rate": (
                    strategy_stats["successes"] / strategy_stats["attempts"]
                    if strategy_stats["attempts"] > 0 else 0.0
                )
            }
            
        return stats

    async def _handle_match_error(self, *args, **kwargs):
        # Minimal error handler for abstract method
        pass

    async def _specific_matches(self, *args, **kwargs):
        # Minimal match logic for abstract method
        return []

    async def adapt_to_context(self, context):
        # Minimal adaptation logic (already present, but ensure implemented)
        pass

class TreeSitterCrossProjectPatternLearner(TreeSitterPatternLearner):
    """Pattern learner that analyzes patterns across multiple projects for tree-sitter."""
    
    def __init__(
        self,
        name: str = "tree_sitter_cross_project_learner",
        config: Optional[Dict[str, Any]] = None,
        insights_dir: Optional[str] = None
    ):
        """Initialize tree-sitter cross project pattern learner.
        
        Args:
            name: Name of the pattern learner
            config: Optional configuration
            insights_dir: Optional directory to store insights
        """
        super().__init__()
        
        # Initialize caches for parsers and patterns
        self._ts_parsers = {}
        self._analyzed_patterns = set()
        self._insights = {}
        
        # Storage for learned patterns
        self.insights_dir = insights_dir or os.path.join(os.getcwd(), "pattern_insights")
        os.makedirs(self.insights_dir, exist_ok=True)
        
        # Get learning strategies
        self._learning_strategies = get_learning_strategies()
        
        if config is None:
            config = {}
        # Configure enabled strategies
        self._enabled_strategies = config.get("enabled_strategies", [
            "node_pattern_improvement",
            "capture_optimization",
            "predicate_refinement",
            "pattern_generalization"
        ])
    
    async def validate_learned_pattern(
        self,
        pattern: Dict[str, Any],
        source_code: str,
        language_id: str
    ) -> PatternValidationResult:
        """Validate a learned pattern against source code.
        
        Args:
            pattern: The learned pattern to validate
            source_code: The source code to validate against
            language_id: Language ID for the pattern
            
        Returns:
            PatternValidationResult: Validation result
        """
        try:
            # Create a temporary pattern for validation
            temp_pattern_name = f"temp_learned_{int(time.time())}"
            
            # Create appropriate pattern type based on pattern data
            if pattern.get("needs_resilience", False):
                # Create resilient pattern
                test_pattern = TreeSitterResilientPattern(
                    name=temp_pattern_name,
                    pattern=pattern["pattern"],
                    category=PatternCategory(pattern.get("category", "code_patterns")),
                    purpose=PatternPurpose(pattern.get("purpose", "UNDERSTANDING")),
                    language_id=language_id,
                    confidence=pattern.get("confidence", 0.7),
                    regex_pattern=pattern.get("regex_fallback", None),
                    metadata={"learned": True, "validation": "cross_project_learner"}
                )
                
                # Use resilient validation
                return await test_pattern.validate_with_recovery(source_code)
                
            elif pattern.get("needs_adaptation", False):
                # Create adaptive pattern
                test_pattern = TreeSitterAdaptivePattern(
                    name=temp_pattern_name,
                    pattern=pattern["pattern"],
                    category=PatternCategory(pattern.get("category", "code_patterns")),
                    purpose=PatternPurpose(pattern.get("purpose", "UNDERSTANDING")),
                    language_id=language_id,
                    confidence=pattern.get("confidence", 0.7),
                    regex_pattern=pattern.get("regex_fallback", None),
                    metadata={"learned": True, "validation": "cross_project_learner"}
                )
                
                # Use adaptive validation
                return await test_pattern.validate_and_adapt(source_code)
                
            else:
                # Create basic tree-sitter pattern
                test_pattern = TreeSitterPattern(
                    name=temp_pattern_name,
                    pattern=pattern["pattern"],
                    category=PatternCategory(pattern.get("category", "code_patterns")),
                    purpose=PatternPurpose(pattern.get("purpose", "UNDERSTANDING")),
                    language_id=language_id,
                    confidence=pattern.get("confidence", 0.7),
                    metadata={"learned": True, "validation": "cross_project_learner"}
                )
                
                # Use standard validation
                return await test_pattern.validate(source_code)
                
        except Exception as e:
            await log(
                f"Error validating learned pattern: {e}",
                level="error",
                context={
                    "learner": self.name,
                    "language_id": language_id,
                    "pattern": pattern.get("pattern", "")[:100] + "..." if pattern.get("pattern", "") and len(pattern.get("pattern", "")) > 100 else pattern.get("pattern", ""),
                    "error_type": type(e).__name__
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[f"Validation error: {str(e)}"]
            )
    
    async def validate_pattern_improvements(
        self,
        original_pattern: str,
        improved_pattern: str,
        test_cases: List[Dict[str, str]],
        language_id: str
    ) -> Dict[str, Any]:
        """Validate that improvements to a pattern maintain or enhance matching.
        
        Args:
            original_pattern: The original tree-sitter pattern
            improved_pattern: The improved tree-sitter pattern
            test_cases: List of test cases to validate against
            language_id: Language ID for the pattern
            
        Returns:
            Dict[str, Any]: Validation results including improvement metrics
        """
        results = {
            "original_valid": True,
            "improved_valid": True,
            "match_improvement": 0.0,
            "test_cases": {},
            "validation_summary": ""
        }
        
        # Create temporary patterns
        temp_original = TreeSitterPattern(
            name=f"original_{int(time.time())}",
            pattern=original_pattern,
            language_id=language_id,
            metadata={"validation": "improvement_test"}
        )
        
        temp_improved = TreeSitterPattern(
            name=f"improved_{int(time.time())}",
            pattern=improved_pattern,
            language_id=language_id,
            metadata={"validation": "improvement_test"}
        )
        
        # Validate against each test case
        total_original_matches = 0
        total_improved_matches = 0
        
        for i, test_case in enumerate(test_cases):
            if "code" not in test_case:
                results["test_cases"][f"test_{i}"] = {
                    "valid": False,
                    "error": "No code in test case"
                }
                continue
                
            # Test original pattern
            original_result = await temp_original.test(test_case["code"])
            original_valid = original_result.get("success", False)
            original_matches = len(original_result.get("matches", []))
            total_original_matches += original_matches
            
            # Test improved pattern
            improved_result = await temp_improved.test(test_case["code"])
            improved_valid = improved_result.get("success", False)
            improved_matches = len(improved_result.get("matches", []))
            total_improved_matches += improved_matches
            
            # Compare results
            results["test_cases"][f"test_{i}"] = {
                "original_valid": original_valid,
                "original_matches": original_matches,
                "improved_valid": improved_valid,
                "improved_matches": improved_matches,
                "improvement": improved_matches - original_matches,
                "code_snippet": test_case["code"][:100] + "..." if len(test_case["code"]) > 100 else test_case["code"]
            }
        
        # Calculate overall improvement
        if total_original_matches > 0:
            match_improvement = (total_improved_matches - total_original_matches) / total_original_matches
            results["match_improvement"] = match_improvement
        else:
            results["match_improvement"] = 1.0 if total_improved_matches > 0 else 0.0
            
        # Check if improved pattern is valid for all test cases
        improved_valid_all = all(case.get("improved_valid", False) for case in results["test_cases"].values())
        original_valid_all = all(case.get("original_valid", False) for case in results["test_cases"].values())
        
        results["original_valid"] = original_valid_all
        results["improved_valid"] = improved_valid_all
        
        # Generate validation summary
        if not improved_valid_all:
            results["validation_summary"] = "Improvement fails on some test cases"
        elif not original_valid_all and improved_valid_all:
            results["validation_summary"] = "Significant improvement - now matches all test cases"
        elif results["match_improvement"] > 0.2:
            results["validation_summary"] = "Substantial match improvement"
        elif results["match_improvement"] > 0:
            results["validation_summary"] = "Modest match improvement"
        elif results["match_improvement"] == 0:
            results["validation_summary"] = "No change in matching"
        else:
            results["validation_summary"] = "Regression in matching capability"
            
        return results

    async def learn_from_repository(
        self,
        repository_path: str,
        language_id: str,
        patterns: List[Union[TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern]] = None,
        sample_limit: int = 100
    ) -> Dict[str, Any]:
        """Learn patterns from a specific repository."""
        results = {
            "repository": repository_path,
            "language_id": language_id,
            "patterns_analyzed": 0,
            "patterns_improved": 0,
            "files_analyzed": 0,
            "improvements": {}
        }
        
        try:
            if not os.path.exists(repository_path):
                await log(f"Repository path does not exist: {repository_path}", level="error")
                return results
            
            if patterns is None or len(patterns) == 0:
                await log(f"No patterns provided for learning", level="info")
                return results
            
            results["patterns_analyzed"] = len(patterns)
            
            # Find relevant files for the language
            language_files = await self._find_language_files(repository_path, language_id, sample_limit)
            
            if not language_files:
                await log(f"No {language_id} files found in repository", level="info")
                return results
            
            results["files_analyzed"] = len(language_files)
            
            # Analyze files to collect insights
            insights = await self._analyze_files(language_files, language_id, patterns)
            
            # Process each pattern
            for pattern in patterns:
                pattern_key = f"{pattern.name}_{language_id}"
                
                # Skip already analyzed patterns to avoid redundant work
                if pattern_key in self._analyzed_patterns:
                    continue
                
                # Apply learning strategies to improve the pattern
                if pattern_key in insights:
                    improved_pattern = await self._improve_pattern(
                        pattern, 
                        insights[pattern_key], 
                        language_id
                    )
                    
                    if improved_pattern:
                        results["patterns_improved"] += 1
                        results["improvements"][pattern.name] = improved_pattern
                
                self._analyzed_patterns.add(pattern_key)
            
            # Store insights for future use
            insights_file = os.path.join(
                self.insights_dir,
                f"insights_{language_id}_{int(time.time())}.json"
            )
            
            with open(insights_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            return results
            
        except Exception as e:
            await log(
                f"Error learning from repository: {e}",
                level="error",
                context={
                    "repository": repository_path,
                    "language_id": language_id
                }
            )
            return results
            
    async def _find_language_files(
        self,
        repository_path: str,
        language_id: str,
        limit: int = 100
    ) -> List[str]:
        """Find files for a specific language in the repository."""
        file_extensions = {
            "python": [".py"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
            "java": [".java"],
            "csharp": [".cs"],
            "cpp": [".cpp", ".cc", ".cxx", ".h", ".hpp"],
            "ruby": [".rb"],
            "go": [".go"],
            "rust": [".rs"],
            "php": [".php"],
            "swift": [".swift"],
            "kotlin": [".kt", ".kts"]
        }
        
        extensions = file_extensions.get(language_id.lower(), [])
        if not extensions:
            await log(f"No known extensions for language: {language_id}", level="warning")
            return []
        
        matching_files = []
        
        for root, _, files in os.walk(repository_path):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    matching_files.append(file_path)
                    
                    if len(matching_files) >= limit:
                        return matching_files
        
        return matching_files
    
    async def _analyze_files(
        self,
        files: List[str],
        language_id: str,
        patterns: List[Union[TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze files to gather pattern insights."""
        insights: Dict[str, Dict[str, Any]] = {}
        
        # Initialize insights for each pattern
        for pattern in patterns:
            pattern_key = f"{pattern.name}_{language_id}"
            insights[pattern_key] = {
                "matches": [],
                "structure_frequencies": defaultdict(int),
                "capture_frequencies": defaultdict(int),
                "node_type_frequencies": defaultdict(int),
                "predicates_success": defaultdict(lambda: {"success": 0, "failure": 0}),
                "pattern_confidence": pattern.confidence
            }
        
        # Get tree-sitter parser
        ts_parser = await get_ts_parser(language_id)
        if not ts_parser:
            return insights
        
        # Process each file
        for file_path in files:
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                # Skip empty or excessively large files
                if not content or len(content) > 500000:  # 500KB limit
                    continue
                
                # Parse with tree-sitter
                tree = ts_parser.parse(content)
                if not tree or not tree.root_node:
                    continue
                
                # Create context
                context = TreeSitterPatternContext(
                    language_id=language_id,
                    file_path=file_path,
                    file_type=FileType.CODE,
                    code_structure={
                        "ast": tree.root_node,
                        "language_id": language_id
                    }
                )
                
                # Match each pattern and collect insights
                for pattern in patterns:
                    pattern_key = f"{pattern.name}_{language_id}"
                    
                    # Try to match the pattern
                    matches = await pattern.matches(content, context)
                    
                    if matches:
                        # Extract insights from matches
                        insights[pattern_key]["matches"].extend(matches[:10])  # Limit to 10 matches per file
                        
                        # Analyze tree-sitter node structures
                        for match in matches:
                            # Collect node type frequencies
                            if "node" in match and match["node"]:
                                node_type = match["node"].type
                                insights[pattern_key]["node_type_frequencies"][node_type] += 1
                            
                            # Collect capture information
                            for capture_name, captures in match.get("captures", {}).items():
                                insights[pattern_key]["capture_frequencies"][capture_name] += 1
                                
                                # Analyze capture node types
                                for capture in captures:
                                    if "type" in capture:
                                        node_type = capture["type"]
                                        insights[pattern_key]["node_type_frequencies"][node_type] += 1
                                        
                                        # Track structure frequencies (capture name + node type)
                                        structure_key = f"{capture_name}:{node_type}"
                                        insights[pattern_key]["structure_frequencies"][structure_key] += 1
                    
                    # Track predicate success rates if available in match data
                    if hasattr(pattern, "pattern") and pattern.pattern:
                        # Extract predicates from pattern
                        predicates = self._extract_predicates(pattern.pattern)
                        for predicate in predicates:
                            # Check if predicate was successful in this file's context
                            success = any(m.get("predicate_results", {}).get(predicate, False) for m in matches)
                            if success:
                                insights[pattern_key]["predicates_success"][predicate]["success"] += 1
                            else:
                                insights[pattern_key]["predicates_success"][predicate]["failure"] += 1
                
            except Exception as e:
                await log(
                    f"Error analyzing file {file_path}: {e}", 
                    level="warning"
                )
                continue
        
        return insights
    
    async def _improve_pattern(
        self,
        pattern: Union[TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern],
        insights: Dict[str, Any],
        language_id: str
    ) -> Optional[Dict[str, Any]]:
        """Improve a pattern based on collected insights.
        
        Args:
            pattern: Pattern to improve
            insights: Insights collected for the pattern
            language_id: Language ID
            
        Returns:
            Dictionary with improved pattern and confidence if improved
        """
        # Skip if no insights or matches
        if not insights or not insights.get("matches"):
            return None
        
        original_pattern = pattern.pattern
        improved_pattern = original_pattern
        confidence = insights.get("pattern_confidence", 0.5)
        
        # Apply learning strategies in order
        for strategy_name in self._enabled_strategies:
            if strategy_name not in self._learning_strategies:
                continue
                
            strategy = self._learning_strategies[strategy_name]
            
            try:
                strategy_result = await strategy.apply(improved_pattern, insights, language_id)
                if strategy_result:
                    improved_pattern = strategy_result["pattern"]
                    confidence = max(confidence, strategy_result.get("confidence", confidence))
            except Exception as e:
                await log(
                    f"Error applying strategy {strategy_name}: {e}", 
                    level="warning",
                    context={"pattern_name": pattern.name}
                )
        
        # Only return if pattern was actually improved
        if improved_pattern != original_pattern:
            # Validate improved pattern
            if await self._validate_pattern(improved_pattern, language_id):
                return {
                    "pattern": improved_pattern,
                    "confidence": confidence,
                    "original_pattern": original_pattern,
                    "strategies_applied": self._enabled_strategies
                }
            else:
                await log(
                    f"Improved pattern for {pattern.name} failed validation", 
                    level="warning"
                )
        
        return None
    
    async def _validate_pattern(self, pattern: str, language_id: str) -> bool:
        """Validate a tree-sitter pattern to ensure it compiles.
        
        Args:
            pattern: Tree-sitter pattern to validate
            language_id: Language ID
            
        Returns:
            True if pattern is valid, False otherwise
        """
        ts_parser = await get_ts_parser(language_id)
        if not ts_parser:
            return False
            
        try:
            # Try to compile the query
            query = ts_parser.compile_query(pattern)
            return query is not None
        except Exception as e:
            await log(
                f"Pattern validation failed: {e}", 
                level="warning",
                context={"language_id": language_id}
            )
            return False
    
    def _extract_predicates(self, pattern: str) -> List[str]:
        """Extract predicates from a tree-sitter pattern.
        
        Args:
            pattern: Tree-sitter pattern
            
        Returns:
            List of predicates in the pattern
        """
        import re
        return re.findall(r'(#\w+\?\s+@\w+\s+(?:"[^"]*"|\S+))', pattern)
    
    def _simplify_pattern(self, pattern: str) -> Optional[str]:
        """Simplify a tree-sitter pattern to create a fallback version.
        
        Args:
            pattern: Original pattern
            
        Returns:
            Simplified pattern or None
        """
        try:
            # Start with the original pattern
            simplified = pattern
            
            # Remove optional nodes (those with ? suffix)
            simplified = re.sub(r'\([^)]+\)\?', '', simplified)
            
            # Remove predicates
            simplified = re.sub(r'#\w+\?\s+@\w+\s+(?:"[^"]*"|\S+)', '', simplified)
            
            # Remove nested depth beyond 2 levels
            # This is a simplification - real implementation would need to parse and modify
            # the pattern structure properly
            
            # If the pattern is unchanged or empty after simplification, return None
            if simplified == pattern or not simplified.strip():
                return None
                
            return simplified
            
        except Exception:
            return None

# Export enhanced pattern types
__all__ = [
    "TreeSitterPatternContext",
    "TreeSitterPatternPerformanceMetrics",
    "TreeSitterPattern",
    "TreeSitterAdaptivePattern",
    "TreeSitterResilientPattern",
    "TreeSitterCrossProjectPatternLearner"
] 