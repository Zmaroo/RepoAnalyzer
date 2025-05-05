"""Query patterns for SQL files.

This module provides SQL-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import (
    COMMON_PATTERNS, COMMON_CAPABILITIES, 
    process_tree_sitter_pattern, validate_tree_sitter_pattern, create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern,
    TreeSitterCrossProjectPatternLearner
)
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache
from utils.cache import cache_coordinator
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time
from .learning_strategies import get_learning_strategies

# Language identifier
LANGUAGE_ID = "sql"

# SQL capabilities (extends common capabilities)
SQL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DATA_MANIPULATION,
    AICapability.QUERY_OPTIMIZATION,
    AICapability.SCHEMA_DESIGN
}

@dataclass
class SQLPatternContext(PatternContext):
    """SQL-specific pattern context."""
    table_names: Set[str] = field(default_factory=set)
    view_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    procedure_names: Set[str] = field(default_factory=set)
    has_transactions: bool = False
    has_indexes: bool = False
    has_triggers: bool = False
    has_constraints: bool = False
    has_joins: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.table_names)}:{self.has_transactions}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "table": PatternPerformanceMetrics(),
    "view": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "procedure": PatternPerformanceMetrics(),
    "query": PatternPerformanceMetrics()
}

SQL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "table": TreeSitterResilientPattern(
                pattern="""
                [
                    (create_table_statement
                        name: (identifier) @syntax.table.name
                        definition: (column_definition_list) @syntax.table.columns) @syntax.table.def,
                    (alter_table_statement
                        name: (identifier) @syntax.alter.table.name
                        action: (_) @syntax.alter.table.action) @syntax.alter.table.def
                ]
                """,
                extract=lambda node: {
                    "type": "table",
                    "name": (
                        node["captures"].get("syntax.table.name", {}).get("text", "") or
                        node["captures"].get("syntax.alter.table.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.table.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.alter.table.def", {}).get("start_point", [0])[0]
                    ),
                    "is_alter": "syntax.alter.table.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["column", "constraint", "index"],
                        PatternRelationType.REFERENCED_BY: ["view", "query"]
                    }
                },
                name="table",
                description="Matches SQL table declarations",
                examples=["CREATE TABLE users (id INT PRIMARY KEY)", "ALTER TABLE orders ADD COLUMN status TEXT"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "view": TreeSitterResilientPattern(
                pattern="""
                [
                    (create_view_statement
                        name: (identifier) @syntax.view.name
                        query: (select_statement) @syntax.view.query) @syntax.view.def,
                    (alter_view_statement
                        name: (identifier) @syntax.alter.view.name
                        query: (select_statement) @syntax.alter.view.query) @syntax.alter.view.def
                ]
                """,
                extract=lambda node: {
                    "type": "view",
                    "name": (
                        node["captures"].get("syntax.view.name", {}).get("text", "") or
                        node["captures"].get("syntax.alter.view.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.view.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.alter.view.def", {}).get("start_point", [0])[0]
                    ),
                    "is_alter": "syntax.alter.view.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["table", "view"],
                        PatternRelationType.REFERENCED_BY: ["query"]
                    }
                },
                name="view",
                description="Matches SQL view declarations",
                examples=["CREATE VIEW active_users AS SELECT * FROM users", "ALTER VIEW order_summary RENAME TO orders"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["view"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": TreeSitterResilientPattern(
                pattern="""
                [
                    (create_function_statement
                        name: (identifier) @syntax.func.name
                        parameters: (parameter_list)? @syntax.func.params
                        returns: (_)? @syntax.func.return
                        body: (_) @syntax.func.body) @syntax.func.def,
                    (create_procedure_statement
                        name: (identifier) @syntax.proc.name
                        parameters: (parameter_list)? @syntax.proc.params
                        body: (_) @syntax.proc.body) @syntax.proc.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.proc.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.proc.def", {}).get("start_point", [0])[0]
                    ),
                    "is_procedure": "syntax.proc.def" in node["captures"],
                    "has_params": (
                        "syntax.func.params" in node["captures"] or
                        "syntax.proc.params" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["query", "statement"],
                        PatternRelationType.DEPENDS_ON: ["table", "view"]
                    }
                },
                name="function",
                description="Matches SQL function and procedure declarations",
                examples=["CREATE FUNCTION get_total() RETURNS INT", "CREATE PROCEDURE update_status(id INT)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.QUERIES: {
            "query": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (select_statement
                        from: (from_clause
                            tables: (_)+ @query.from.tables) @query.from
                        join: (join_clause)* @query.join
                        where: (where_clause)? @query.where
                        group: (group_by_clause)? @query.group
                        having: (having_clause)? @query.having
                        order: (order_by_clause)? @query.order) @query.select,
                    (insert_statement
                        table: (identifier) @query.insert.table
                        columns: (column_list)? @query.insert.columns
                        values: (_) @query.insert.values) @query.insert,
                    (update_statement
                        table: (identifier) @query.update.table
                        set: (set_clause) @query.update.set
                        where: (where_clause)? @query.update.where) @query.update
                ]
                """,
                extract=lambda node: {
                    "type": "query",
                    "line_number": (
                        node["captures"].get("query.select", {}).get("start_point", [0])[0] or
                        node["captures"].get("query.insert", {}).get("start_point", [0])[0] or
                        node["captures"].get("query.update", {}).get("start_point", [0])[0]
                    ),
                    "is_select": "query.select" in node["captures"],
                    "is_insert": "query.insert" in node["captures"],
                    "is_update": "query.update" in node["captures"],
                    "has_joins": "query.join" in node["captures"],
                    "relationships": {
                        PatternRelationType.USES: ["table", "view", "function"],
                        PatternRelationType.DEPENDS_ON: ["column"]
                    }
                },
                name="query",
                description="Matches SQL query statements",
                examples=["SELECT * FROM users JOIN orders", "INSERT INTO logs VALUES (?)", "UPDATE status SET active = 1"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.QUERIES,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["query"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "unconstrained_query": QueryPattern(
            name="unconstrained_query",
            pattern=r'SELECT\s+.*\s+FROM\s+[^;]+(?:(?!WHERE).)*;',
            extract=lambda m: {
                "type": "unconstrained_query",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects queries without WHERE clause", "examples": ["SELECT * FROM users;"]}
        ),
        "sql_injection": QueryPattern(
            name="sql_injection",
            pattern=r"'[^']*\s*(?:\+|\|\|)\s*[^']*'",
            extract=lambda m: {
                "type": "sql_injection",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potential SQL injection vulnerabilities", "examples": ["'SELECT * FROM users WHERE id = ' + user_input"]}
        ),
        "cartesian_product": QueryPattern(
            name="cartesian_product",
            pattern=r'FROM\s+([^;]+?),\s*([^;]+?)(?:\s+WHERE|\s*;)',
            extract=lambda m: {
                "type": "cartesian_product",
                "tables": [m.group(1), m.group(2)],
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects implicit cartesian products", "examples": ["SELECT * FROM table1, table2;"]}
        ),
        "unindexed_join": QueryPattern(
            name="unindexed_join",
            pattern=r'JOIN\s+([^;]+?)\s+ON\s+([^;]+?)(?:\s+WHERE|\s*;)',
            extract=lambda m: {
                "type": "unindexed_join",
                "table": m.group(1),
                "condition": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potentially unindexed joins", "examples": ["JOIN large_table ON id = ref_id"]}
        ),
        "unsafe_delete": QueryPattern(
            name="unsafe_delete",
            pattern=r'DELETE\s+FROM\s+[^;]+(?:(?!WHERE).)*;',
            extract=lambda m: {
                "type": "unsafe_delete",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects DELETE without WHERE clause", "examples": ["DELETE FROM users;"]}
        )
    }
}

class SQLPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced SQL pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
        self._learning_strategies = get_learning_strategies()
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": [],
            "strategy_metrics": {}
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with SQL-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("sql", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register SQL patterns
        await self._pattern_processor.register_language_patterns(
            "sql", 
            SQL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "sql_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SQL_PATTERNS),
                "capabilities": list(SQL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="sql",
                file_type=FileType.CODE,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add SQL-specific patterns
            async with AsyncErrorBoundary("sql_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "sql",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                sql_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(sql_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "sql_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "sql_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def _learn_patterns_from_features(self, features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Learn patterns from extracted features with strategy application."""
        patterns = await super()._learn_patterns_from_features(features)
        
        # Apply learning strategies to improve patterns
        improved_patterns = []
        for pattern_data in patterns:
            pattern_str = pattern_data.get("pattern", "")
            insights = pattern_data.get("insights", {})
            
            # Try each strategy in sequence
            for strategy_name, strategy in self._learning_strategies.items():
                try:
                    improved = await strategy.apply(pattern_str, insights, "sql")
                    if improved:
                        pattern_data["pattern"] = improved["pattern"]
                        pattern_data["confidence"] = improved["confidence"]
                        
                        # Update strategy metrics
                        if strategy_name not in self._metrics["strategy_metrics"]:
                            self._metrics["strategy_metrics"][strategy_name] = {
                                "attempts": 0,
                                "improvements": 0,
                                "success_rate": 0.0
                            }
                        
                        metrics = self._metrics["strategy_metrics"][strategy_name]
                        metrics["attempts"] += 1
                        metrics["improvements"] += 1
                        metrics["success_rate"] = metrics["improvements"] / metrics["attempts"]
                
                except Exception as e:
                    await log(
                        f"Error applying {strategy_name} strategy: {e}",
                        level="warning",
                        context={"language": "sql"}
                    )
            
            improved_patterns.append(pattern_data)
        
        return improved_patterns

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status with strategy metrics
            await global_health_monitor.update_component_status(
                "sql_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics,
                    "strategy_metrics": self._metrics["strategy_metrics"]
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "sql_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

# Initialize caches
pattern_cache = UnifiedCache("sql_patterns", eviction_policy="lru")
context_cache = UnifiedCache("sql_contexts", eviction_policy="lru")

@cached_in_request
async def get_sql_pattern_cache():
    """Get the SQL pattern cache from the coordinator."""
    return await cache_coordinator.get_cache("sql_patterns")

@cached_in_request
async def get_sql_context_cache():
    """Get the SQL context cache from the coordinator."""
    return await cache_coordinator.get_cache("sql_contexts")

async def initialize_sql_patterns():
    """Initialize SQL patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Initialize caches through coordinator
    await cache_coordinator.register_cache("sql_patterns", pattern_cache)
    await cache_coordinator.register_cache("sql_contexts", context_cache)
    
    # Register cache warmup functions
    analytics = await get_cache_analytics()
    analytics.register_warmup_function(
        "sql_patterns",
        _warmup_pattern_cache
    )
    analytics.register_warmup_function(
        "sql_contexts",
        _warmup_context_cache
    )
    
    # Register patterns and initialize learner
    await pattern_processor.register_language_patterns(
        "sql",
        SQL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SQL_CAPABILITIES
        }
    )
    
    pattern_learner = await SQLPatternLearner.create()
    await pattern_processor.register_pattern_learner("sql", pattern_learner)
    
    await global_health_monitor.update_component_status(
        "sql_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SQL_PATTERNS),
            "capabilities": list(SQL_CAPABILITIES)
        }
    )

async def _warmup_pattern_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for pattern cache."""
    results = {}
    for key in keys:
        try:
            patterns = SQL_PATTERNS.get(PatternCategory.SYNTAX, {})
            if patterns:
                results[key] = patterns
        except Exception as e:
            await log(f"Error warming up pattern cache for {key}: {e}", level="warning")
    return results

async def _warmup_context_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for context cache."""
    results = {}
    for key in keys:
        try:
            context = await create_sql_pattern_context("", {})
            results[key] = context.__dict__
        except Exception as e:
            await log(f"Error warming up context cache for {key}: {e}", level="warning")
    return results

@handle_async_errors(error_types=ProcessingError)
async def process_sql_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a SQL pattern with full system integration."""
    # Try pattern cache first
    cache_key = f"sql_pattern_{pattern.name}_{hash(source_code)}"
    pattern_cache = await get_sql_pattern_cache()
    cached_result = await pattern_cache.get_async(cache_key)
    if cached_result:
        return cached_result
        
    # Then check request cache
    request_cache = get_current_request_cache()
    if request_cache:
        request_cached = await request_cache.get(cache_key)
        if request_cached:
            return request_cached
    
    # Process pattern if not cached
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        # Cache results
        await pattern_cache.set_async(cache_key, common_result)
        if request_cache:
            await request_cache.set(cache_key, common_result)
        return common_result
    
    # Rest of the existing processing logic...
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("sql", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "sql", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_tree_sitter_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"sql_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "sql",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
            block_matches = await pattern.matches(block.content)
            if block_matches:
                # Extract features for each match
                for match in block_matches:
                    features = await feature_extractor.extract_features(
                        block.content,
                        match
                    )
                    match["features"] = features
                    match["block"] = block.__dict__
                matches.extend(block_matches)
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_sql_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "sql_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_sql_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create SQL-specific pattern context with tree-sitter integration.
    
    This function creates a tree-sitter based context for SQL patterns
    with full system integration.
    """
    # Create a base tree-sitter context
    base_context = await create_tree_sitter_context(
        file_path,
        code_structure,
        language_id=LANGUAGE_ID,
        learned_patterns=learned_patterns
    )
    
    # Add SQL-specific information
    base_context.language_stats = {"language": LANGUAGE_ID}
    base_context.relevant_patterns = list(SQL_PATTERNS.keys())
    
    # Add system integration metadata
    base_context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return base_context

def update_sql_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in PATTERN_METRICS:
        pattern_metrics = PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_sql_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=PATTERN_RELATIONSHIPS.get(pattern_name, []),
        performance=PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "sql"}
    )

# Initialize pattern learner
pattern_learner = SQLPatternLearner()

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "table": {
        PatternRelationType.CONTAINS: ["column", "constraint", "index"],
        PatternRelationType.REFERENCED_BY: ["view", "query"]
    },
    "view": {
        PatternRelationType.DEPENDS_ON: ["table", "view"],
        PatternRelationType.REFERENCED_BY: ["query"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["query", "statement"],
        PatternRelationType.DEPENDS_ON: ["table", "view"]
    },
    "query": {
        PatternRelationType.USES: ["table", "view", "function"],
        PatternRelationType.DEPENDS_ON: ["column"]
    }
}

# Export public interfaces
__all__ = [
    'SQL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_sql_pattern_context',
    'get_sql_pattern_match_result',
    'update_sql_pattern_metrics',
    'SQLPatternLearner',
    'process_sql_pattern',
    'LANGUAGE_ID'
] 