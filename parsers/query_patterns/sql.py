"""Query patterns for SQL files.

This module provides SQL-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.logger import log

# Language identifier
LANGUAGE = "sql"

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
            "table": ResilientPattern(
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
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["table"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "view": ResilientPattern(
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
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["view"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
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
                language_id=LANGUAGE,
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
            "query": AdaptivePattern(
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
                language_id=LANGUAGE,
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
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_sql_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from SQL content for repository learning."""
    patterns = []
    context = SQLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SQL_PATTERNS:
                category_patterns = SQL_PATTERNS[category]
                for purpose in category_patterns:
                    for pattern_name, pattern in category_patterns[purpose].items():
                        if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "purpose": purpose.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "table":
                                        context.table_names.add(match["name"])
                                    elif match["type"] == "view":
                                        context.view_names.add(match["name"])
                                    elif match["type"] == "function":
                                        if match["is_procedure"]:
                                            context.procedure_names.add(match["name"])
                                        else:
                                            context.function_names.add(match["name"])
                                    elif match["type"] == "query":
                                        if match["has_joins"]:
                                            context.has_joins = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting SQL patterns: {e}", level="error")
    
    return patterns

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
    'extract_sql_patterns_for_learning',
    'SQLPatternContext',
    'pattern_learner'
] 