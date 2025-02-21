"""SQL-specific Tree-sitter patterns."""

from .common import COMMON_PATTERNS

SQL_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "function": {
            "pattern": """
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
            "extract": lambda node: {
                "name": node["captures"].get("syntax.function.name", {}).get("text", "") or
                       node["captures"].get("syntax.procedure.name", {}).get("text", ""),
                "type": "function" if "syntax.function.def" in node["captures"] else "procedure"
            }
        },
        
        "table": {
            "pattern": """
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
            "extract": lambda node: {
                "name": node["captures"].get("syntax.table.name", {}).get("text", "") or
                       node["captures"].get("syntax.view.name", {}).get("text", ""),
                "type": "table" if "syntax.table.def" in node["captures"] else "view"
            }
        }
    },
    
    "semantics": {
        "type": {
            "pattern": """
            [
                (data_type
                    name: (_) @semantics.type.name
                    parameters: [(number) (identifier)]* @semantics.type.param) @semantics.type.def,
                
                (array_type
                    type: (_) @semantics.type.array.base
                    size: (_)? @semantics.type.array.size) @semantics.type.array
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.type.name", {}).get("text", ""),
                "params": [p.get("text", "") for p in node["captures"].get("semantics.type.param", [])]
            }
        }
    },
    
    "structure": {
        "schema": {
            "pattern": """
            [
                (create_schema
                    name: (identifier) @structure.schema.name
                    authorization: (identifier)? @structure.schema.owner) @structure.schema.def,
                
                (create_database
                    name: (identifier) @structure.database.name
                    options: (_)? @structure.database.options) @structure.database.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("structure.schema.name", {}).get("text", "") or
                       node["captures"].get("structure.database.name", {}).get("text", ""),
                "type": "schema" if "structure.schema.def" in node["captures"] else "database"
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (block_comment) @documentation.block,
                (line_comment) @documentation.line
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment", {}).get("text", "") or
                       node["captures"].get("documentation.block", {}).get("text", "") or
                       node["captures"].get("documentation.line", {}).get("text", "")
            }
        }
    }
} 