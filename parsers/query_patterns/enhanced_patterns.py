"""Enhanced pattern functionality for RepoAnalyzer.

This module provides advanced pattern capabilities that enhance the existing
query patterns with features like context awareness, learning, and error recovery.
"""

from typing import Dict, Any, List, Optional, Set, TypeVar, Generic
from dataclasses import dataclass, field
import asyncio
import time
from collections import defaultdict
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    QueryPattern, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, FileType, ParserType
)
from parsers.base_parser import BaseParser
from parsers.block_extractor import BlockExtractor, ExtractedBlock
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
from utils.logger import log
from utils.cache import LRUCache
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from db.transaction import transaction_scope

@dataclass
class PatternContext:
    """Context information for pattern matching."""
    code_structure: Dict[str, Any] = field(default_factory=dict)  # AST structure info
    language_stats: Dict[str, int] = field(default_factory=dict)  # Language usage statistics
    project_patterns: List[str] = field(default_factory=list)     # Common patterns in project
    file_location: str = ""                                       # File path/module location
    dependencies: Set[str] = field(default_factory=set)           # Project dependencies
    recent_changes: List[Dict] = field(default_factory=list)      # Recent file modifications
    extracted_blocks: List[ExtractedBlock] = field(default_factory=list)  # Extracted code blocks
    parser_type: ParserType = ParserType.UNKNOWN                  # Parser type being used
    
    def get_context_key(self) -> str:
        """Generate a unique key for this context."""
        return f"{self.file_location}:{len(self.dependencies)}:{len(self.project_patterns)}:{self.parser_type.value}"

class PatternPerformanceMetrics:
    """Track pattern performance metrics."""
    
    def __init__(self):
        self.total_uses = 0
        self.successful_matches = 0
        self.failed_matches = 0
        self.execution_times: List[float] = []
        self.context_performance: Dict[str, Dict[str, float]] = {}
        self.false_positives = 0
        self.last_updated = time.time()
        self.parser_stats: Dict[ParserType, Dict[str, int]] = {
            ParserType.TREE_SITTER: defaultdict(int),
            ParserType.CUSTOM: defaultdict(int)
        }
    
    def update(
        self,
        success: bool,
        execution_time: float,
        context_key: Optional[str] = None,
        parser_type: Optional[ParserType] = None
    ):
        """Update metrics with new data."""
        self.total_uses += 1
        if success:
            self.successful_matches += 1
        else:
            self.failed_matches += 1
        self.execution_times.append(execution_time)
        
        if context_key:
            if context_key not in self.context_performance:
                self.context_performance[context_key] = {
                    "uses": 0,
                    "successes": 0,
                    "avg_time": 0.0
                }
            
            perf = self.context_performance[context_key]
            perf["uses"] += 1
            if success:
                perf["successes"] += 1
            perf["avg_time"] = (perf["avg_time"] * (perf["uses"] - 1) + execution_time) / perf["uses"]
        
        if parser_type:
            stats = self.parser_stats[parser_type]
            stats["total"] += 1
            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
            
        self.last_updated = time.time()
    
    @property
    def success_rate(self) -> float:
        """Get overall success rate."""
        return self.successful_matches / self.total_uses if self.total_uses > 0 else 0.0
    
    @property
    def avg_execution_time(self) -> float:
        """Get average execution time."""
        return sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0.0

class AdaptivePattern(QueryPattern):
    """Self-improving pattern with learning capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = PatternPerformanceMetrics()
        self.adaptations: List[Dict[str, Any]] = []
        self._pattern_cache = LRUCache(1000)
        self._block_extractor = None
        self._base_parser = None
    
    async def initialize(self):
        """Initialize required components."""
        if not self._block_extractor:
            from parsers.block_extractor import get_block_extractor
            self._block_extractor = await get_block_extractor()
        
        if not self._base_parser:
            self._base_parser = await BaseParser.create(
                self.language_id,
                FileType.CODE,
                ParserType.TREE_SITTER if self.is_tree_sitter else ParserType.CUSTOM
            )
    
    async def matches(
        self,
        source_code: str,
        context: Optional[PatternContext] = None
    ) -> List[Dict[str, Any]]:
        """Get matches with adaptation and learning."""
        await self.initialize()
        start_time = time.time()
        context_key = context.get_context_key() if context else None
        parser_type = context.parser_type if context else ParserType.UNKNOWN
        
        try:
            # Check if we should adapt
            if context and self.should_adapt(context):
                await self.adapt_to_context(context)
            
            # Try cache first
            cache_key = f"{hash(source_code)}:{context_key or ''}"
            if cached := await self._pattern_cache.get(cache_key):
                return cached
            
            # Extract blocks if available
            blocks = []
            if context and context.extracted_blocks:
                blocks = context.extracted_blocks
            else:
                # Parse with base parser
                ast = await self._base_parser._parse_source(source_code)
                if ast:
                    blocks = await self._block_extractor.get_child_blocks(
                        self.language_id,
                        source_code,
                        ast["root"] if "root" in ast else ast
                    )
            
            # Get matches from blocks
            matches = []
            if blocks:
                for block in blocks:
                    block_matches = await self._match_block(block, context)
                    if block_matches:
                        matches.extend(block_matches)
            
            # If no blocks or no matches, try full source
            if not matches:
                matches = await super().matches(source_code)
            
            # Update metrics
            execution_time = time.time() - start_time
            self.metrics.update(bool(matches), execution_time, context_key, parser_type)
            
            # Cache result
            await self._pattern_cache.set(cache_key, matches)
            
            return matches
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.metrics.update(False, execution_time, context_key, parser_type)
            await log(f"Error in adaptive pattern matching: {e}", level="error")
            return []
    
    async def _match_block(
        self,
        block: ExtractedBlock,
        context: Optional[PatternContext]
    ) -> List[Dict[str, Any]]:
        """Match pattern against a code block."""
        try:
            if self.is_tree_sitter:
                return await self._tree_sitter_block_match(block, context)
            else:
                return await self._custom_block_match(block, context)
        except Exception as e:
            await log(f"Error matching block: {e}", level="error")
            return []
    
    async def _tree_sitter_block_match(
        self,
        block: ExtractedBlock,
        context: Optional[PatternContext]
    ) -> List[Dict[str, Any]]:
        """Match block using tree-sitter."""
        try:
            parser = get_parser(self.language_id)
            if not parser:
                return []
            
            tree = parser.parse(bytes(block.content, "utf8"))
            query = get_language(self.language_id).query(self.pattern)
            
            matches = []
            for match in query.matches(tree.root_node):
                match_data = {
                    "node": match.pattern_node,
                    "captures": {c.name: c.node for c in match.captures},
                    "block": block.__dict__
                }
                
                if self.extract:
                    try:
                        extracted = self.extract(match_data)
                        if extracted:
                            match_data.update(extracted)
                    except Exception:
                        pass
                
                matches.append(match_data)
            
            return matches
        except Exception as e:
            await log(f"Error in tree-sitter block matching: {e}", level="error")
            return []
    
    async def _custom_block_match(
        self,
        block: ExtractedBlock,
        context: Optional[PatternContext]
    ) -> List[Dict[str, Any]]:
        """Match block using custom parser."""
        try:
            # Get custom parser class
            parser_class = CUSTOM_PARSER_CLASSES.get(self.language_id)
            if not parser_class:
                return []
            
            # Create parser instance
            parser = parser_class()
            
            # Process block
            matches = []
            try:
                block_matches = await parser.process_pattern(
                    {"pattern": self.pattern, "name": self.name},
                    block.content
                )
                
                for match in block_matches:
                    match_data = {
                        **match,
                        "block": block.__dict__
                    }
                    
                    if self.extract:
                        try:
                            extracted = self.extract(match_data)
                            if extracted:
                                match_data.update(extracted)
                        except Exception:
                            pass
                    
                    matches.append(match_data)
            except Exception as e:
                await log(f"Error processing block with custom parser: {e}", level="error")
            
            return matches
        except Exception as e:
            await log(f"Error in custom block matching: {e}", level="error")
            return []
    
    def should_adapt(self, context: PatternContext) -> bool:
        """Determine if pattern should adapt to context."""
        if context_key := context.get_context_key():
            if perf := self.metrics.context_performance.get(context_key):
                return perf["uses"] > 10 and perf["successes"] / perf["uses"] < 0.5
        return False
    
    async def adapt_to_context(self, context: PatternContext) -> None:
        """Adapt pattern based on context."""
        try:
            if self.is_tree_sitter:
                await self._adapt_tree_sitter_pattern(context)
            else:
                await self._adapt_regex_pattern(context)
            
            self.adaptations.append({
                "timestamp": time.time(),
                "context": context.__dict__,
                "success_rate_before": self.metrics.success_rate
            })
        except Exception as e:
            await log(f"Error adapting pattern: {e}", level="error")
    
    async def _adapt_tree_sitter_pattern(self, context: PatternContext) -> None:
        """Adapt tree-sitter pattern query."""
        # Analyze common structures in context
        common_nodes = self._analyze_common_structures(context)
        
        # Modify pattern to better match common structures
        self.pattern = self._enhance_tree_sitter_query(self.pattern, common_nodes)
    
    async def _adapt_regex_pattern(self, context: PatternContext) -> None:
        """Adapt regex pattern."""
        # Analyze common patterns in context
        common_patterns = self._analyze_common_patterns(context)
        
        # Modify pattern to better match common patterns
        self.pattern = self._enhance_regex_pattern(self.pattern, common_patterns)
    
    def _analyze_common_structures(self, context: PatternContext) -> Dict[str, int]:
        """Analyze common AST structures in context."""
        node_counts = defaultdict(int)
        if "ast" in context.code_structure:
            self._count_node_types(context.code_structure["ast"], node_counts)
        return dict(node_counts)
    
    def _count_node_types(self, node: Dict[str, Any], counts: Dict[str, int]) -> None:
        """Count node types in AST."""
        if isinstance(node, dict):
            if "type" in node:
                counts[node["type"]] += 1
            for value in node.values():
                self._count_node_types(value, counts)
        elif isinstance(node, list):
            for item in node:
                self._count_node_types(item, counts)
    
    def _analyze_common_patterns(self, context: PatternContext) -> List[str]:
        """Analyze common patterns in context."""
        return context.project_patterns

    def _enhance_tree_sitter_query(self, query: str, common_nodes: Dict[str, int]) -> str:
        """Enhance tree-sitter query based on common nodes."""
        # Add most common node types to query if not present
        for node_type, count in sorted(common_nodes.items(), key=lambda x: x[1], reverse=True)[:5]:
            if node_type not in query:
                query = self._add_node_to_query(query, node_type)
        return query
    
    def _enhance_regex_pattern(self, pattern: str, common_patterns: List[str]) -> str:
        """Enhance regex pattern based on common patterns."""
        # Add common patterns as alternatives if they improve matching
        for common_pattern in common_patterns:
            if self._would_improve_matching(pattern, common_pattern):
                pattern = self._add_pattern_alternative(pattern, common_pattern)
        return pattern
    
    def _add_node_to_query(self, query: str, node_type: str) -> str:
        """Add node type to tree-sitter query."""
        # Add node capture if not present
        if f"({node_type}" not in query:
            query = query.replace("[", f"[({node_type}) @{node_type},")
        return query
    
    def _add_pattern_alternative(self, pattern: str, new_pattern: str) -> str:
        """Add alternative to regex pattern."""
        return f"({pattern}|{new_pattern})"
    
    def _would_improve_matching(self, current: str, new_pattern: str) -> bool:
        """Check if adding pattern would improve matching."""
        # Simple heuristic: check if patterns are sufficiently different
        return len(set(current) ^ set(new_pattern)) / len(set(current) | set(new_pattern)) > 0.3

class ResilientPattern(AdaptivePattern):
    """Pattern with advanced error recovery capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_strategies = {
            "syntax_error": self._handle_syntax_error,
            "partial_match": self._handle_partial_match,
            "ambiguous_match": self._handle_ambiguous_match,
            "block_error": self._handle_block_error
        }
        self.recovery_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    async def matches(self, source_code: str, context: Optional[PatternContext] = None) -> List[Dict[str, Any]]:
        """Get matches with error recovery."""
        try:
            return await super().matches(source_code, context)
        except Exception as e:
            error_type = self._classify_error(str(e))
            if strategy := self.error_strategies.get(error_type):
                result = await strategy(source_code, e)
                self.recovery_stats[error_type]["attempts"] += 1
                if result:
                    self.recovery_stats[error_type]["successes"] += 1
                return result
            raise
    
    def _classify_error(self, error_msg: str) -> str:
        """Classify error type."""
        if "syntax" in error_msg.lower():
            return "syntax_error"
        if "partial" in error_msg.lower():
            return "partial_match"
        if "ambiguous" in error_msg.lower():
            return "ambiguous_match"
        return "unknown_error"
    
    async def _handle_syntax_error(self, source_code: str, error: Exception) -> List[Dict[str, Any]]:
        """Handle syntax errors."""
        # Try with more permissive pattern
        relaxed_pattern = self._relax_pattern(self.pattern)
        try:
            if self.is_tree_sitter:
                return await self._tree_sitter_matches(source_code, relaxed_pattern)
            else:
                return await self._regex_matches(source_code, relaxed_pattern)
        except Exception:
            return []
    
    async def _handle_partial_match(self, source_code: str, error: Exception) -> List[Dict[str, Any]]:
        """Handle partial matches."""
        # Try matching smaller chunks
        chunks = self._split_into_chunks(source_code)
        results = []
        for chunk in chunks:
            try:
                chunk_matches = await super().matches(chunk)
                results.extend(self._adjust_positions(chunk_matches, chunk))
            except Exception:
                continue
        return results
    
    async def _handle_ambiguous_match(self, source_code: str, error: Exception) -> List[Dict[str, Any]]:
        """Handle ambiguous matches."""
        # Try most specific match first
        specific_pattern = self._make_pattern_more_specific(self.pattern)
        try:
            return await super().matches(source_code, pattern=specific_pattern)
        except Exception:
            return []
    
    def _relax_pattern(self, pattern: str) -> str:
        """Make pattern more permissive."""
        if self.is_tree_sitter:
            # Make optional parts of the query optional
            return pattern.replace(")", ")?")\
                         .replace("]", "]*")
        else:
            # Make regex more permissive
            return pattern.replace("+", "*")\
                         .replace("{2,}", "*")\
                         .replace("^", "")\
                         .replace("$", "")
    
    def _split_into_chunks(self, source_code: str, chunk_size: int = 1000) -> List[str]:
        """Split source code into manageable chunks."""
        return [source_code[i:i + chunk_size] 
                for i in range(0, len(source_code), chunk_size)]
    
    def _adjust_positions(self, matches: List[Dict[str, Any]], chunk: str) -> List[Dict[str, Any]]:
        """Adjust match positions for chunk."""
        chunk_start = chunk.start() if hasattr(chunk, 'start') else 0
        for match in matches:
            if "start" in match:
                match["start"] += chunk_start
            if "end" in match:
                match["end"] += chunk_start
        return matches
    
    def _make_pattern_more_specific(self, pattern: str) -> str:
        """Make pattern more specific."""
        if self.is_tree_sitter:
            # Add more specific node requirements
            return pattern.replace("(_)", "(identifier)")\
                         .replace("@", "@specific.")
        else:
            # Make regex more specific
            return pattern.replace(".*", "[^\\n]*")\
                         .replace(".+", "[^\\n]+")\
                         .replace("\\w+", "[a-zA-Z_][a-zA-Z0-9_]*")
    
    async def _handle_block_error(
        self,
        block: ExtractedBlock,
        error: Exception
    ) -> List[Dict[str, Any]]:
        """Handle errors in block matching."""
        try:
            # Try with more permissive pattern
            relaxed_pattern = self._relax_pattern(self.pattern)
            
            if self.is_tree_sitter:
                parser = get_parser(self.language_id)
                if parser:
                    tree = parser.parse(bytes(block.content, "utf8"))
                    query = get_language(self.language_id).query(relaxed_pattern)
                    return [
                        {
                            "node": match.pattern_node,
                            "captures": {c.name: c.node for c in match.captures},
                            "block": block.__dict__,
                            "recovered": True
                        }
                        for match in query.matches(tree.root_node)
                    ]
            else:
                # Try with custom parser
                parser_class = CUSTOM_PARSER_CLASSES.get(self.language_id)
                if parser_class:
                    parser = parser_class()
                    matches = await parser.process_pattern(
                        {"pattern": relaxed_pattern, "name": self.name},
                        block.content
                    )
                    return [
                        {**match, "block": block.__dict__, "recovered": True}
                        for match in matches
                    ]
        except Exception as recovery_error:
            await log(f"Error in block error recovery: {recovery_error}", level="error")
        
        return []

class CrossProjectPatternLearner:
    """Learn and share patterns across multiple projects."""
    
    def __init__(self):
        self.pattern_database: Dict[str, Dict[str, Any]] = {}
        self.project_stats: Dict[str, Dict[str, Any]] = {}
        self.similarity_threshold = 0.8
        self._cache = LRUCache(1000)
        self._block_extractor = None
        self._base_parser = None
    
    async def initialize(self):
        """Initialize required components."""
        if not self._block_extractor:
            from parsers.block_extractor import get_block_extractor
            self._block_extractor = await get_block_extractor()
    
    async def learn_from_project(self, project_path: str) -> None:
        """Learn patterns from a project."""
        await self.initialize()
        
        patterns = await self._extract_project_patterns(project_path)
        await self._integrate_patterns(patterns, project_path)
    
    async def suggest_patterns(self, context: PatternContext) -> List[QueryPattern]:
        """Suggest patterns based on cross-project learning."""
        similar_contexts = await self._find_similar_contexts(context)
        return await self._get_successful_patterns(similar_contexts)
    
    async def _extract_project_patterns(self, project_path: str) -> List[Dict[str, Any]]:
        """Extract patterns from a project."""
        try:
            # Get blocks from project files
            blocks = []
            async with AsyncErrorBoundary("project_pattern_extraction"):
                # Extract blocks from files
                for file_path, source_code in await self._get_project_files(project_path):
                    try:
                        file_blocks = await self._block_extractor.get_child_blocks(
                            self._get_language_id(file_path),
                            source_code,
                            None  # Let block extractor handle parsing
                        )
                        blocks.extend(file_blocks)
                    except Exception as e:
                        await log(f"Error extracting blocks from {file_path}: {e}", level="error")
            
            # Convert blocks to patterns
            patterns = []
            for block in blocks:
                try:
                    pattern = await self._convert_block_to_pattern(block)
                    if pattern:
                        patterns.append(pattern)
                except Exception as e:
                    await log(f"Error converting block to pattern: {e}", level="error")
            
            return patterns
        except Exception as e:
            await log(f"Error extracting project patterns: {e}", level="error")
            return []
    
    async def _integrate_patterns(self, patterns: List[Dict[str, Any]], project_path: str) -> None:
        """Integrate new patterns into database."""
        async with transaction_scope() as txn:
            for pattern in patterns:
                pattern_key = f"{pattern['name']}:{pattern['language_id']}"
                if pattern_key not in self.pattern_database:
                    self.pattern_database[pattern_key] = {
                        "pattern": pattern,
                        "projects": set(),
                        "success_rate": 0.0,
                        "uses": 0
                    }
                self.pattern_database[pattern_key]["projects"].add(project_path)
    
    async def _find_similar_contexts(self, context: PatternContext) -> List[str]:
        """Find contexts similar to given context."""
        similar = []
        context_key = context.get_context_key()
        
        for project, stats in self.project_stats.items():
            if self._context_similarity(context, stats["context"]) > self.similarity_threshold:
                similar.append(project)
        
        return similar
    
    def _context_similarity(self, context1: PatternContext, context2: Dict[str, Any]) -> float:
        """Calculate similarity between contexts."""
        # Compare dependencies
        dep_similarity = len(set(context1.dependencies) & set(context2.get("dependencies", []))) / \
                        len(set(context1.dependencies) | set(context2.get("dependencies", []))) \
                        if context1.dependencies or context2.get("dependencies") else 0.0
        
        # Compare patterns
        pattern_similarity = len(set(context1.project_patterns) & set(context2.get("patterns", []))) / \
                           len(set(context1.project_patterns) | set(context2.get("patterns", []))) \
                           if context1.project_patterns or context2.get("patterns") else 0.0
        
        return (dep_similarity + pattern_similarity) / 2
    
    async def _get_successful_patterns(self, similar_contexts: List[str]) -> List[QueryPattern]:
        """Get successful patterns from similar contexts."""
        successful_patterns = []
        
        for pattern_info in self.pattern_database.values():
            if any(context in pattern_info["projects"] for context in similar_contexts):
                if pattern_info["success_rate"] > 0.7:  # Only suggest highly successful patterns
                    pattern = pattern_info["pattern"]
                    successful_patterns.append(
                        ResilientPattern(
                            name=pattern["name"],
                            pattern=pattern["pattern"],
                            category=pattern["category"],
                            purpose=pattern["purpose"],
                            language_id=pattern["language_id"],
                            confidence=pattern_info["success_rate"]
                        )
                    )
        
        return successful_patterns

# Export enhanced pattern types
__all__ = [
    'PatternContext',
    'PatternPerformanceMetrics',
    'AdaptivePattern',
    'ResilientPattern',
    'CrossProjectPatternLearner'
] 