"""[6.6] Database schema management.

This module provides centralized schema management for all databases:
1. Table creation and deletion
2. Index management
3. Vector storage setup
4. Schema validation
"""

import asyncio
from typing import Set
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    DatabaseError,
    PostgresError,
    Neo4jError,
    ErrorBoundary,
    ErrorSeverity
)
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.async_runner import submit_async_task
from db.connection import connection_manager

class SchemaError(DatabaseError):
    """Schema management specific errors."""
    pass

class SchemaManager:
    """Manages database schema operations."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._pending_tasks: Set[asyncio.Future] = set()
        self._retry_manager = DatabaseRetryManager(
            RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
        )
    
    async def _execute_query(self, sql: str) -> None:
        """Execute a SQL query with task tracking."""
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                future = submit_async_task(conn.execute(sql))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    @handle_async_errors(error_types=(SchemaError, PostgresError))
    async def drop_all_tables(self) -> None:
        """[6.6.4] Clean database state."""
        async with self._lock:
            try:
                # Drop in correct order for foreign key constraints
                tables = [
                    "code_patterns", "doc_patterns", "arch_patterns",
                    "repo_doc_relations", "doc_versions", "doc_clusters",
                    "repo_docs", "code_snippets", "repositories"
                ]
                
                for table in tables:
                    await self._execute_query(f"DROP TABLE IF EXISTS {table} CASCADE;")
                
                log("✅ All existing database tables dropped!")
            except Exception as e:
                log(f"Error dropping tables: {e}", level="error")
                raise SchemaError(f"Failed to drop tables: {str(e)}")
    
    async def create_repositories_table(self) -> None:
        """Create repositories table."""
        sql = """
        CREATE TABLE IF NOT EXISTS repositories (
            id SERIAL PRIMARY KEY,
            repo_name TEXT UNIQUE NOT NULL,
            source_url TEXT,
            repo_type TEXT DEFAULT 'active',  -- 'active' or 'reference'
            active_repo_id INTEGER,           -- If this is a reference repo, stores the ID of the active repo it is associated with.
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_active_repo
                FOREIGN KEY(active_repo_id)
                    REFERENCES repositories(id)
                    ON DELETE SET NULL
        );
        """
        await self._execute_query(sql)
    
    async def create_code_snippets_table(self) -> None:
        """[6.6.1] Create code storage with vector similarity support."""
        sql = """
        CREATE TABLE IF NOT EXISTS code_snippets (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            ast TEXT,
            embedding VECTOR(768),  -- GraphCodeBERT dimension
            enriched_features JSONB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_id, file_path)
        );
        CREATE INDEX IF NOT EXISTS idx_code_snippets_embedding 
        ON code_snippets USING ivfflat (embedding vector_cosine_ops);
        """
        await self._execute_query(sql)
    
    async def create_repo_docs_table(self) -> None:
        """[6.6.2] Create documentation storage with versioning."""
        sql_table = """
        CREATE TABLE IF NOT EXISTS repo_docs (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            content TEXT NOT NULL,
            doc_type TEXT NOT NULL,  -- 'markdown', 'inline', 'docstring'
            version INTEGER DEFAULT 1,
            cluster_id INTEGER,
            related_code_path TEXT,  -- For linking to specific code files
            embedding VECTOR(768) NULL,
            metadata JSONB,
            quality_metrics JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self._execute_query(sql_table)
        
        # Vector similarity index
        sql_index = """
        CREATE INDEX IF NOT EXISTS idx_repo_docs_embedding 
        ON repo_docs USING ivfflat (embedding vector_cosine_ops);
        """
        await self._execute_query(sql_index)
    
    async def create_repo_doc_relations_table(self) -> None:
        """Create junction table for repo-doc relationships."""
        sql = """
        CREATE TABLE IF NOT EXISTS repo_doc_relations (
            repo_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
            doc_id INTEGER REFERENCES repo_docs(id) ON DELETE CASCADE,
            is_primary BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (repo_id, doc_id)
        );
        """
        await self._execute_query(sql)
    
    async def create_doc_versions_table(self) -> None:
        """Track document versions."""
        sql = """
        CREATE TABLE IF NOT EXISTS doc_versions (
            id SERIAL PRIMARY KEY,
            doc_id INTEGER REFERENCES repo_docs(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            version INTEGER NOT NULL,
            changes_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(doc_id, version)
        );
        """
        await self._execute_query(sql)
    
    async def create_doc_clusters_table(self) -> None:
        """Group related documentation."""
        sql = """
        CREATE TABLE IF NOT EXISTS doc_clusters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self._execute_query(sql)
    
    async def create_code_patterns_table(self) -> None:
        """[6.6.7] Create code patterns table for reference repository learning."""
        sql = """
        CREATE TABLE IF NOT EXISTS code_patterns (
            pattern_id SERIAL PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            language TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            elements JSONB NOT NULL,
            sample TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_id, file_path, pattern_type)
        );
        """
        await self._execute_query(sql)
    
    async def create_doc_patterns_table(self) -> None:
        """[6.6.8] Create documentation patterns table for reference repository learning."""
        sql = """
        CREATE TABLE IF NOT EXISTS doc_patterns (
            pattern_id SERIAL PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            doc_type TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            count INTEGER NOT NULL,
            samples TEXT[] NOT NULL,
            common_structure JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_id, doc_type, pattern_type)
        );
        """
        await self._execute_query(sql)
    
    async def create_arch_patterns_table(self) -> None:
        """[6.6.9] Create architecture patterns table for reference repository learning."""
        sql = """
        CREATE TABLE IF NOT EXISTS arch_patterns (
            pattern_id SERIAL PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            pattern_type TEXT NOT NULL,
            directory_structure JSONB,
            top_level_dirs TEXT[],
            dependencies JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(repo_id, pattern_type)
        );
        """
        await self._execute_query(sql)
    
    @handle_async_errors(error_types=(SchemaError, PostgresError, Neo4jError))
    async def create_all_tables(self) -> None:
        """[6.6.3] Initialize all database tables."""
        async with self._lock:
            try:
                async with AsyncErrorBoundary("schema creation", error_types=(SchemaError, PostgresError, Neo4jError)):
                    # Initialize connections
                    await connection_manager.initialize_postgres()
                    await connection_manager.initialize()
                    
                    # Create PostgreSQL tables in order of dependencies
                    tables = [
                        self.create_repositories_table,
                        self.create_code_snippets_table,
                        self.create_repo_docs_table,
                        self.create_repo_doc_relations_table,
                        self.create_doc_versions_table,
                        self.create_doc_clusters_table,
                        self.create_code_patterns_table,
                        self.create_doc_patterns_table,
                        self.create_arch_patterns_table
                    ]
                    
                    for create_table in tables:
                        future = submit_async_task(create_table())
                        self._pending_tasks.add(future)
                        try:
                            await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                    
                    # Create Neo4j schema
                    session = await connection_manager.get_session()
                    try:
                        # Create indexes for different node types
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (c:Code) ON (c.repo_id, c.file_path)")
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Documentation) ON (d.repo_id, d.path)")
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (r:Repository) ON (r.id)")
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (l:Language) ON (l.name)")
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (p:Pattern) ON (p.id)")
                        await session.run("CREATE INDEX IF NOT EXISTS FOR (f:Feature) ON (f.name)")
                        
                        # Create constraints for uniqueness
                        await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE")
                        await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Code) REQUIRE (c.repo_id, c.file_path) IS UNIQUE")
                        await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE")
                    finally:
                        await session.close()
                    
                    log("✅ Schema initialization complete")
            except Exception as e:
                error_msg = f"Schema initialization failed: {str(e)}"
                log(error_msg, level="error")
                raise SchemaError(error_msg)
    
    async def cleanup(self) -> None:
        """Clean up any pending tasks."""
        if self._pending_tasks:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
            self._pending_tasks.clear()

# Create global schema manager instance
schema_manager = SchemaManager()