"""PostgreSQL database check utility.

This module provides utilities for checking PostgreSQL database tables and their contents.
"""

import asyncio
from pprint import pprint
from utils.error_handling import (
    handle_async_errors,
    ErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from utils.logger import log
from db.psql import query
from db.connection import connection_manager
from utils.async_runner import submit_async_task, get_loop
from utils.app_init import register_shutdown_handler

@handle_async_errors(error_types=[PostgresError])
async def check_all_postgres_tables():
    """Check and display contents of all PostgreSQL tables."""
    print("\n==========================================")
    print("     PostgreSQL Database Check")
    print("==========================================\n")
    
    # Dictionary defining table names and their corresponding queries
    tables = {
        "Repositories": "SELECT * FROM repositories ORDER BY id;",
        "Code Snippets": "SELECT * FROM code_snippets ORDER BY id;",
        "Repository Documents": "SELECT * FROM repo_docs ORDER BY id;",
        "Repo Doc Relations": "SELECT * FROM repo_doc_relations ORDER BY repo_id, doc_id;",
        "Document Versions": "SELECT * FROM doc_versions ORDER BY id;",
        "Document Clusters": "SELECT * FROM doc_clusters ORDER BY id;"
    }
    
    tasks = []
    try:
        # Initialize PostgreSQL connection
        await connection_manager.initialize_postgres()
        
        for table_name, sql in tables.items():
            with ErrorBoundary(
                error_types=[PostgresError, Exception],
                error_message=f"Error querying {table_name}",
                severity=ErrorSeverity.ERROR
            ) as error_boundary:
                future = submit_async_task(query(sql))
                tasks.append((table_name, future))
        
        # Wait for all queries to complete
        for table_name, future in tasks:
            try:
                records = await asyncio.wrap_future(future)
                print(f"{table_name}:")
                print("-" * len(table_name))
                print(f"Total entries: {len(records)}")
                for record in records:
                    pprint(dict(record))
                print("\n")
            except Exception as e:
                log(f"Error querying {table_name}: {e}", level="error")
                print(f"Error querying {table_name}: {e}")
    finally:
        # Close all connections
        await connection_manager.cleanup()

# Register cleanup handler
async def cleanup_check():
    """Cleanup check utility resources."""
    try:
        await connection_manager.cleanup()
        log("Check utility resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up check utility resources: {e}", level="error")

register_shutdown_handler(cleanup_check)

if __name__ == "__main__":
    loop = get_loop()
    future = submit_async_task(check_all_postgres_tables())
    loop.run_until_complete(future)