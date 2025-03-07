"""SQL-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

SQL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (create_function
                        name: (identifier) @syntax.function.name
                        parameters: (parameter_list
                            [(parameter
                                name: (identifier) @syntax.function.param.name
                                type: (_) @syntax.function.param.type
                                default: (_)? @syntax.function.param.default)]*) @syntax.function.params
                        return_type: (_)? @syntax.function.return_type
                        body: (_) @syntax.function.body) @syntax.function.def,
                    
                    (create_procedure
                        name: (identifier) @syntax.procedure.name
                        parameters: (parameter_list
                            [(parameter
                                name: (identifier) @syntax.procedure.param.name
                                type: (_) @syntax.procedure.param.type
                                default: (_)? @syntax.procedure.param.default)]*) @syntax.procedure.params
                        body: (_) @syntax.procedure.body) @syntax.procedure.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                           node["captures"].get("syntax.procedure.name", {}).get("text", ""),
                    "type": "function" if "syntax.function.def" in node["captures"] else "procedure"
                },
                description="Matches SQL function and procedure definitions",
                examples=[
                    "CREATE FUNCTION get_balance(account_id INT) RETURNS DECIMAL",
                    "CREATE PROCEDURE update_balance(account_id INT, amount DECIMAL)"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "table": QueryPattern(
                pattern="""
                [
                    (create_table
                        name: (identifier) @syntax.table.name
                        definition: (column_definitions
                            [(column_definition
                                name: (identifier) @syntax.table.column.name
                                type: (_) @syntax.table.column.type
                                constraints: [(constraint
                                    type: (_) @syntax.table.column.constraint.type
                                    expression: (_)? @syntax.table.column.constraint.expr)]*) @syntax.table.column]*) @syntax.table.columns) @syntax.table.def,
                    
                    (create_view
                        name: (identifier) @syntax.view.name
                        query: (_) @syntax.view.query) @syntax.view.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.table.name", {}).get("text", "") or
                           node["captures"].get("syntax.view.name", {}).get("text", ""),
                    "type": "table" if "syntax.table.def" in node["captures"] else "view"
                },
                description="Matches SQL table and view definitions",
                examples=[
                    "CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(255))",
                    "CREATE VIEW active_users AS SELECT * FROM users WHERE active = 1"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "type": QueryPattern(
                pattern="""
                [
                    (data_type
                        name: (_) @semantics.type.name
                        parameters: [(number) (identifier)]* @semantics.type.param) @semantics.type.def,
                    
                    (array_type
                        type: (_) @semantics.type.array.base
                        size: (_)? @semantics.type.array.size) @semantics.type.array
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                    "params": [p.get("text", "") for p in node["captures"].get("semantics.type.param", [])]
                },
                description="Matches SQL data type definitions",
                examples=[
                    "VARCHAR(255)",
                    "DECIMAL(10,2)",
                    "INT[]"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "schema": QueryPattern(
                pattern="""
                [
                    (create_schema
                        name: (identifier) @structure.schema.name
                        authorization: (identifier)? @structure.schema.owner) @structure.schema.def,
                    
                    (create_database
                        name: (identifier) @structure.database.name
                        options: (_)? @structure.database.options) @structure.database.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("structure.schema.name", {}).get("text", "") or
                           node["captures"].get("structure.database.name", {}).get("text", ""),
                    "type": "schema" if "structure.schema.def" in node["captures"] else "database"
                },
                description="Matches SQL schema and database definitions",
                examples=[
                    "CREATE SCHEMA accounting",
                    "CREATE DATABASE customers"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": QueryPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.block,
                    (line_comment) @documentation.line
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                           node["captures"].get("documentation.block", {}).get("text", "") or
                           node["captures"].get("documentation.line", {}).get("text", "")
                },
                description="Matches SQL comments",
                examples=[
                    "-- Single line comment",
                    "/* Block comment */",
                    "/** Documentation comment */"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for SQL
SQL_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "query_patterns": QueryPattern(
                pattern="""
                [
                    (select_statement
                        select_clause: (select_clause
                            columns: [(column_reference) (alias) (wildcard)]+ @query.select.columns
                            distinct: (distinct_clause)? @query.select.distinct) @query.select
                        from_clause: (from_clause
                            tables: [(table_reference) (alias)]+ @query.from.tables) @query.from
                        where_clause: (where_clause
                            condition: (_) @query.where.condition)? @query.where
                        group_by_clause: (group_by_clause)? @query.group
                        having_clause: (having_clause)? @query.having
                        order_by_clause: (order_by_clause)? @query.order
                        limit_clause: (limit_clause)? @query.limit) @query.statement,
                        
                    (join_clause
                        type: [(inner_join) (left_join) (right_join) (full_join)] @query.join.type
                        table: [(table_reference) (alias)] @query.join.table
                        condition: (_) @query.join.condition) @query.join,
                        
                    (subquery
                        select_statement: (select_statement) @query.subquery.select) @query.subquery,
                        
                    (common_table_expression
                        name: (identifier) @query.cte.name
                        select_statement: (select_statement) @query.cte.select) @query.cte
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "query_patterns",
                    "is_select": "query.statement" in node["captures"],
                    "is_join": "query.join" in node["captures"],
                    "is_subquery": "query.subquery" in node["captures"],
                    "is_cte": "query.cte" in node["captures"],
                    "has_where": "query.where" in node["captures"] and node["captures"].get("query.where", {}).get("text", "") != "",
                    "has_group_by": "query.group" in node["captures"] and node["captures"].get("query.group", {}).get("text", "") != "",
                    "has_having": "query.having" in node["captures"] and node["captures"].get("query.having", {}).get("text", "") != "",
                    "has_order_by": "query.order" in node["captures"] and node["captures"].get("query.order", {}).get("text", "") != "",
                    "has_limit": "query.limit" in node["captures"] and node["captures"].get("query.limit", {}).get("text", "") != "",
                    "join_type": node["captures"].get("query.join.type", {}).get("text", ""),
                    "cte_name": node["captures"].get("query.cte.name", {}).get("text", ""),
                    "query_type": (
                        "select" if "query.statement" in node["captures"] else
                        "join" if "query.join" in node["captures"] else
                        "subquery" if "query.subquery" in node["captures"] else
                        "cte" if "query.cte" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches SQL query patterns",
                examples=[
                    "SELECT * FROM users WHERE active = 1",
                    "INNER JOIN orders ON users.id = orders.user_id",
                    "WITH active_users AS (SELECT * FROM users WHERE active = 1)"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "data_definition": QueryPattern(
                pattern="""
                [
                    (create_table_statement
                        name: (identifier) @ddl.table.name
                        definition: (column_definition_list
                            (column_definition
                                name: (identifier) @ddl.table.column.name
                                type: (_) @ddl.table.column.type)+ @ddl.table.columns) @ddl.table.definition) @ddl.table,
                        
                    (create_index_statement
                        name: (identifier) @ddl.index.name
                        table: (identifier) @ddl.index.table
                        columns: (column_list) @ddl.index.columns) @ddl.index,
                        
                    (create_view_statement
                        name: (identifier) @ddl.view.name
                        select_statement: (select_statement) @ddl.view.select) @ddl.view,
                        
                    (alter_table_statement
                        name: (identifier) @ddl.alter.table
                        action: [(add_column_clause) (drop_column_clause) (add_constraint_clause)] @ddl.alter.action) @ddl.alter
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "data_definition",
                    "is_create_table": "ddl.table" in node["captures"],
                    "is_create_index": "ddl.index" in node["captures"],
                    "is_create_view": "ddl.view" in node["captures"],
                    "is_alter_table": "ddl.alter" in node["captures"],
                    "object_name": (
                        node["captures"].get("ddl.table.name", {}).get("text", "") or
                        node["captures"].get("ddl.index.name", {}).get("text", "") or
                        node["captures"].get("ddl.view.name", {}).get("text", "") or
                        node["captures"].get("ddl.alter.table", {}).get("text", "")
                    ),
                    "column_count": len(node["captures"].get("ddl.table.column.name", [])) if "ddl.table.columns" in node["captures"] else 0,
                    "ddl_type": (
                        "create_table" if "ddl.table" in node["captures"] else
                        "create_index" if "ddl.index" in node["captures"] else
                        "create_view" if "ddl.view" in node["captures"] else
                        "alter_table" if "ddl.alter" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches SQL DDL patterns",
                examples=[
                    "CREATE TABLE users (id INT, name VARCHAR(255))",
                    "CREATE INDEX idx_name ON users(name)",
                    "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "data_manipulation": QueryPattern(
                pattern="""
                [
                    (insert_statement
                        table: (identifier) @dml.insert.table
                        columns: (column_list)? @dml.insert.columns
                        values: (_) @dml.insert.values) @dml.insert,
                        
                    (update_statement
                        table: (identifier) @dml.update.table
                        set_clause: (set_clause) @dml.update.set
                        where_clause: (where_clause)? @dml.update.where) @dml.update,
                        
                    (delete_statement
                        table: (identifier) @dml.delete.table
                        where_clause: (where_clause)? @dml.delete.where) @dml.delete,
                        
                    (merge_statement
                        target: (identifier) @dml.merge.target
                        source: (identifier) @dml.merge.source
                        condition: (_) @dml.merge.condition) @dml.merge
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "data_manipulation",
                    "is_insert": "dml.insert" in node["captures"],
                    "is_update": "dml.update" in node["captures"],
                    "is_delete": "dml.delete" in node["captures"],
                    "is_merge": "dml.merge" in node["captures"],
                    "table_name": (
                        node["captures"].get("dml.insert.table", {}).get("text", "") or
                        node["captures"].get("dml.update.table", {}).get("text", "") or
                        node["captures"].get("dml.delete.table", {}).get("text", "") or
                        node["captures"].get("dml.merge.target", {}).get("text", "")
                    ),
                    "has_where": (
                        ("dml.update" in node["captures"] and "dml.update.where" in node["captures"] and node["captures"].get("dml.update.where", {}).get("text", "") != "") or
                        ("dml.delete" in node["captures"] and "dml.delete.where" in node["captures"] and node["captures"].get("dml.delete.where", {}).get("text", "") != "")
                    ),
                    "dml_type": (
                        "insert" if "dml.insert" in node["captures"] else
                        "update" if "dml.update" in node["captures"] else
                        "delete" if "dml.delete" in node["captures"] else
                        "merge" if "dml.merge" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches SQL DML patterns",
                examples=[
                    "INSERT INTO users (name, email) VALUES ('John', 'john@example.com')",
                    "UPDATE users SET active = 1 WHERE id = 1",
                    "DELETE FROM users WHERE active = 0"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "procedural_sql": QueryPattern(
                pattern="""
                [
                    (create_function_statement
                        name: (identifier) @proc.function.name
                        parameters: (parameter_list) @proc.function.params
                        return_type: (_) @proc.function.return
                        body: (_) @proc.function.body) @proc.function,
                        
                    (create_procedure_statement
                        name: (identifier) @proc.procedure.name
                        parameters: (parameter_list) @proc.procedure.params
                        body: (_) @proc.procedure.body) @proc.procedure,
                        
                    (if_statement
                        condition: (_) @proc.if.condition
                        then_statement: (_) @proc.if.then
                        else_statement: (_)? @proc.if.else) @proc.if,
                        
                    (loop_statement
                        body: (_) @proc.loop.body) @proc.loop,
                        
                    (variable_declaration
                        name: (identifier) @proc.var.name
                        type: (_) @proc.var.type
                        default: (_)? @proc.var.default) @proc.var
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "procedural_sql",
                    "is_function": "proc.function" in node["captures"],
                    "is_procedure": "proc.procedure" in node["captures"],
                    "is_if": "proc.if" in node["captures"],
                    "is_loop": "proc.loop" in node["captures"],
                    "is_variable": "proc.var" in node["captures"],
                    "name": (
                        node["captures"].get("proc.function.name", {}).get("text", "") or
                        node["captures"].get("proc.procedure.name", {}).get("text", "") or
                        node["captures"].get("proc.var.name", {}).get("text", "")
                    ),
                    "has_else": "proc.if.else" in node["captures"] and node["captures"].get("proc.if.else", {}).get("text", "") != "",
                    "procedural_type": (
                        "function" if "proc.function" in node["captures"] else
                        "procedure" if "proc.procedure" in node["captures"] else
                        "if_statement" if "proc.if" in node["captures"] else
                        "loop" if "proc.loop" in node["captures"] else
                        "variable" if "proc.var" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches SQL procedural patterns",
                examples=[
                    "CREATE FUNCTION get_balance() RETURNS DECIMAL",
                    "IF balance > 0 THEN RETURN true; ELSE RETURN false; END IF;",
                    "DECLARE v_count INTEGER DEFAULT 0;"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
SQL_PATTERNS.update(SQL_PATTERNS_FOR_LEARNING) 