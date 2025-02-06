"""Tree-sitter patterns for SQL."""

SQL_PATTERNS = {
    # Basic pattern for function detection
    "function": """
        [
          (function_definition)
          (procedure_definition)
        ] @function
    """,
    # Extended pattern for detailed function information
    "function_details": """
        [
          (function_definition
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
             body: (compound_statement) @function.body) @function.def,
          (procedure_definition
             name: (identifier) @function.name
             parameters: (parameter_list)? @function.params
             body: (compound_statement) @function.body) @function.def
        ]
    """,
    # Query patterns
    "query": """
        [
          (select_statement) @query.select
          (insert_statement) @query.insert
          (update_statement) @query.update
          (delete_statement) @query.delete
        ]
    """,
    # Detailed query components
    "query_details": """
        [
          (select_statement
            select_clause: (select_clause
              columns: [
                (selected_column
                  expression: (_) @query.select.column
                  alias: (alias)? @query.select.alias)*
              ]) @query.select.columns
            from_clause: (from_clause
              tables: [
                (table_reference
                  table: (_) @query.from.table
                  alias: (alias)? @query.from.alias)*
              ])? @query.from
            where_clause: (where_clause
              condition: (_) @query.where.condition)? @query.where
            group_by_clause: (group_by_clause)? @query.group_by
            having_clause: (having_clause)? @query.having
            order_by_clause: (order_by_clause)? @query.order_by
            limit_clause: (limit_clause)? @query.limit) @query.statement,
          (insert_statement
            table: (identifier) @query.insert.table
            columns: (column_list)? @query.insert.columns
            values: (_) @query.insert.values) @query.statement,
          (update_statement
            table: (identifier) @query.update.table
            set_clause: (set_clause)? @query.update.set
            where_clause: (where_clause)? @query.update.where) @query.statement,
          (delete_statement
            table: (identifier) @query.delete.table
            where_clause: (where_clause)? @query.delete.where) @query.statement
        ]
    """,
    # Table definitions
    "table": """
        [
          (create_table_statement
            name: (identifier) @table.name
            definition: (table_definition
              columns: (column_definition_list)? @table.columns
              constraints: (table_constraint_list)? @table.constraints) @table.def) @table
        ]
    """,
    # View definitions
    "view": """
        [
          (create_view_statement
            name: (identifier) @view.name
            query: (select_statement) @view.query) @view
        ]
    """,
    # Index definitions
    "index": """
        [
          (create_index_statement
            name: (identifier) @index.name
            table: (identifier) @index.table
            columns: (index_column_list) @index.columns) @index
        ]
    """
} 