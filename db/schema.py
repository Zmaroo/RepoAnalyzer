"""[6.6] Database schema management.

This module provides centralized schema management for all databases:
1. Table creation and deletion
2. Index management
3. Vector storage setup
4. Schema validation
"""

import asyncio
from typing import Set, Dict, Any, List, Optional
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    DatabaseError,
    PostgresError,
    Neo4jError,
    ErrorAudit,
    ErrorSeverity
)
from db.retry_utils import RetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from db.connection import connection_manager
from utils.shutdown import register_shutdown_handler
from db.transaction import transaction_scope
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_database
from utils.cache import UnifiedCache, cache_coordinator
import time

class SchemaError(DatabaseError):
    """Schema management specific errors."""
    pass

class SchemaManager:
    """Manages database schema operations."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._retry_manager = None
        self._cache = None
        self._metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "operation_times": []
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise DatabaseError("SchemaManager not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'SchemaManager':
        """Async factory method to create and initialize a SchemaManager instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="schema manager initialization",
                error_types=DatabaseError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize retry manager
                instance._retry_manager = await RetryManager.create(
                    RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("schema_manager")
                await cache_coordinator.register_cache("schema_manager", instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component(
                    "schema_manager",
                    health_check=instance._check_health
                )
                
                instance._initialized = True
                await log("Schema manager initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing schema manager: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise DatabaseError(f"Failed to initialize schema manager: {e}")
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for schema manager."""
        # Calculate average operation time
        avg_op_time = sum(self._metrics["operation_times"]) / len(self._metrics["operation_times"]) if self._metrics["operation_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_operations": self._metrics["total_operations"],
                "success_rate": self._metrics["successful_operations"] / self._metrics["total_operations"] if self._metrics["total_operations"] > 0 else 0,
                "cache_hit_rate": self._metrics["cache_hits"] / (self._metrics["cache_hits"] + self._metrics["cache_misses"]) if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0 else 0,
                "avg_operation_time": avg_op_time
            }
        }
        
        # Check for degraded conditions
        if details["metrics"]["success_rate"] < 0.8:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Low operation success rate"
        elif avg_op_time > 1.0:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High operation times"
        
        return {
            "status": status,
            "details": details
        }
    
    async def _execute_query(self, sql: str) -> None:
        """Execute a SQL query with task tracking."""
        if not self._initialized:
            await self.ensure_initialized()
            
        task = asyncio.create_task(connection_manager.get_postgres_connection())
        self._pending_tasks.add(task)
        try:
            conn = await task
            try:
                async with conn.transaction():
                    task = asyncio.create_task(conn.execute(sql))
                    self._pending_tasks.add(task)
                    try:
                        await task
                    finally:
                        self._pending_tasks.remove(task)
            finally:
                task = asyncio.create_task(connection_manager.release_postgres_connection(conn))
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
        finally:
            self._pending_tasks.remove(task)
    
    @handle_async_errors(error_types=(SchemaError, PostgresError))
    async def drop_all_tables(self) -> None:
        """[6.6.4] Clean database state."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with self._lock:
            try:
                start_time = time.time()
                self._metrics["total_operations"] += 1
                
                # Drop in correct order for foreign key constraints
                tables = [
                    "code_patterns", "doc_patterns", "arch_patterns",
                    "repo_doc_relations", "doc_versions", "doc_clusters",
                    "repo_docs", "code_snippets", "repositories"
                ]
                
                for table in tables:
                    await self._execute_query(f"DROP TABLE IF EXISTS {table} CASCADE;")
                
                # Record success and timing
                self._metrics["successful_operations"] += 1
                operation_time = time.time() - start_time
                self._metrics["operation_times"].append(operation_time)
                
                # Update health status
                await global_health_monitor.update_component_status(
                    "schema_manager",
                    ComponentStatus.HEALTHY,
                    response_time=operation_time * 1000,  # Convert to ms
                    error=False
                )
                
                log("✅ All existing database tables dropped!")
            except Exception as e:
                self._metrics["failed_operations"] += 1
                log(f"Error dropping tables: {e}", level="error")
                raise SchemaError(f"Failed to drop tables: {str(e)}")
    
    async def create_repositories_table(self, txn) -> None:
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
    
    async def create_code_snippets_table(self, txn) -> None:
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
    
    async def create_repo_docs_table(self, txn) -> None:
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
    
    async def create_repo_doc_relations_table(self, txn) -> None:
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
    
    async def create_doc_versions_table(self, txn) -> None:
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
    
    async def create_doc_clusters_table(self, txn) -> None:
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
    
    async def create_code_patterns_table(self, txn) -> None:
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
    
    async def create_doc_patterns_table(self, txn) -> None:
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
    
    async def create_arch_patterns_table(self, txn) -> None:
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
        if not self._initialized:
            await self.ensure_initialized()
            
        async with self._lock:
            try:
                async with AsyncErrorBoundary("schema creation", error_types=(SchemaError, PostgresError, Neo4jError)):
                    # Initialize connections
                    await connection_manager.initialize_postgres()
                    await connection_manager.initialize()
                    
                    async with transaction_scope(distributed=True) as txn:
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
                            task = asyncio.create_task(create_table(txn))
                            self._pending_tasks.add(task)
                            try:
                                await task
                            finally:
                                self._pending_tasks.remove(task)
                        
                        # Create Neo4j schema
                        await self.create_neo4j_schema(txn)
                        
                        # Record schema creation in transaction metrics
                        await txn.record_operation("create_all_tables", {
                            "postgres_tables": len(tables),
                            "neo4j_schema": True,
                            "timestamp": time.time()
                        })
                    
                    log("✅ Schema initialization complete")
            except Exception as e:
                error_msg = f"Schema initialization failed: {str(e)}"
                log(error_msg, level="error")
                raise SchemaError(error_msg)
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up retry manager
            if self._retry_manager:
                await self._retry_manager.cleanup()
            
            # Clean up cache
            if self._cache:
                await self._cache.clear_async()
                await cache_coordinator.unregister_cache("schema_manager")
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("schema_manager")
            
            self._initialized = False
            await log("Schema manager cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up schema manager: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup schema manager: {e}")

# Global instance
schema_manager = None

async def get_schema_manager() -> SchemaManager:
    """Get the global schema manager instance."""
    global schema_manager
    if not schema_manager:
        schema_manager = await SchemaManager.create()
    return schema_manager

# Register cleanup handler
async def cleanup_schema():
    """Cleanup schema manager resources."""
    try:
        if schema_manager:
            await schema_manager.cleanup()
        await log("Schema manager resources cleaned up", level="info")
    except Exception as e:
        await log(f"Error cleaning up schema manager resources: {e}", level="error")
        raise DatabaseError(f"Failed to cleanup schema manager resources: {e}")

register_shutdown_handler(cleanup_schema)

async def create_all_tables(self):
    """Create all database tables."""
    if self._initialized:
        return
        
    async with transaction_scope() as txn:
        # Create base tables
        await self._create_base_tables(txn)
        
        # Create AI pattern tables
        await self._create_ai_pattern_tables(txn)
        
        # Create indexes
        await self._create_indexes(txn)
        
        self._initialized = True

async def _create_base_tables(self, txn):
    """Create base database tables."""
    # Create repositories table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS repositories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            source_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create files table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER REFERENCES repositories(id),
            path TEXT NOT NULL,
            language TEXT,
            content TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create code snippets table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS code_snippets (
            id SERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES files(id),
            content TEXT NOT NULL,
            language TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create documentation table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS documentation (
            id SERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES files(id),
            content TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

async def _create_ai_pattern_tables(self, txn):
    """Create AI pattern storage tables."""
    # Create code patterns table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS code_patterns (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER REFERENCES repositories(id),
            file_path TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            language TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence FLOAT NOT NULL,
            complexity INTEGER,
            dependencies TEXT[],
            documentation TEXT,
            metadata JSONB,
            embedding VECTOR(1536),
            tree_sitter_type TEXT,
            tree_sitter_language TEXT,
            tree_sitter_metrics JSONB,
            ai_insights JSONB,
            ai_confidence FLOAT,
            ai_metrics JSONB,
            ai_recommendations JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes for tree-sitter fields
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_patterns_tree_sitter_type ON code_patterns(tree_sitter_type);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_tree_sitter_language ON code_patterns(tree_sitter_language);
    """)
    
    # Create documentation patterns table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS doc_patterns (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER REFERENCES repositories(id),
            file_path TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence FLOAT NOT NULL,
            structure JSONB,
            metadata JSONB,
            embedding VECTOR(1536),
            ai_insights JSONB,  -- Store AI-generated insights
            ai_confidence FLOAT,  -- AI confidence in pattern
            ai_metrics JSONB,  -- AI-specific metrics
            ai_recommendations JSONB,  -- AI recommendations
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create architecture patterns table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS arch_patterns (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER REFERENCES repositories(id),
            pattern_type TEXT NOT NULL,
            structure JSONB NOT NULL,
            dependencies JSONB,
            confidence FLOAT NOT NULL,
            metadata JSONB,
            embedding VECTOR(1536),
            ai_insights JSONB,  -- Store AI-generated insights
            ai_confidence FLOAT,  -- AI confidence in pattern
            ai_metrics JSONB,  -- AI-specific metrics
            ai_recommendations JSONB,  -- AI recommendations
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create pattern relationships table with AI enhancements
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_relationships (
            id SERIAL PRIMARY KEY,
            source_pattern_id INTEGER NOT NULL,
            target_pattern_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            strength FLOAT NOT NULL,
            metadata JSONB,
            ai_relationship_type TEXT,  -- AI-detected relationship type
            ai_relationship_strength FLOAT,  -- AI-calculated relationship strength
            ai_insights JSONB,  -- AI insights about the relationship
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_pattern_id, target_pattern_id, relationship_type)
        )
    """)
    
    # Create pattern metrics table with AI enhancements
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_metrics (
            id SERIAL PRIMARY KEY,
            pattern_id INTEGER NOT NULL,
            pattern_type TEXT NOT NULL,
            complexity_score FLOAT,
            maintainability_score FLOAT,
            reusability_score FLOAT,
            usage_count INTEGER DEFAULT 0,
            last_used TIMESTAMP WITH TIME ZONE,
            metadata JSONB,
            ai_quality_score FLOAT,  -- AI-calculated quality score
            ai_impact_score FLOAT,  -- AI-calculated impact score
            ai_trend_analysis JSONB,  -- AI trend analysis
            ai_recommendations JSONB,  -- AI recommendations
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pattern_id, pattern_type)
        )
    """)
    
    # Create pattern learning history table with AI enhancements
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_learning_history (
            id SERIAL PRIMARY KEY,
            repo_id INTEGER REFERENCES repositories(id),
            pattern_id INTEGER NOT NULL,
            pattern_type TEXT NOT NULL,
            learning_type TEXT NOT NULL,
            confidence FLOAT NOT NULL,
            metadata JSONB,
            ai_learning_insights JSONB,  -- AI learning insights
            ai_learning_progress JSONB,  -- AI learning progress tracking
            ai_adaptation_metrics JSONB,  -- AI adaptation metrics
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create pattern cross-repository analysis table
    await txn.execute("""
        CREATE TABLE IF NOT EXISTS pattern_cross_repo_analysis (
            id SERIAL PRIMARY KEY,
            pattern_id INTEGER NOT NULL,
            source_repo_id INTEGER REFERENCES repositories(id),
            target_repo_id INTEGER REFERENCES repositories(id),
            similarity_score FLOAT NOT NULL,
            adaptation_score FLOAT NOT NULL,
            conflict_score FLOAT NOT NULL,
            ai_insights JSONB,  -- AI cross-repo insights
            ai_recommendations JSONB,  -- AI cross-repo recommendations
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pattern_id, source_repo_id, target_repo_id)
        )
    """)

async def _create_indexes(self, txn):
    """Create database indexes."""
    # Create indexes for code patterns
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_patterns_repo_id ON code_patterns(repo_id);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_pattern_type ON code_patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_language ON code_patterns(language);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_confidence ON code_patterns(confidence);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_ai_confidence ON code_patterns(ai_confidence);
        CREATE INDEX IF NOT EXISTS idx_code_patterns_embedding ON code_patterns USING ivfflat (embedding vector_cosine_ops);
    """)
    
    # Create indexes for documentation patterns
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_repo_id ON doc_patterns(repo_id);
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_pattern_type ON doc_patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_doc_type ON doc_patterns(doc_type);
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_confidence ON doc_patterns(confidence);
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_ai_confidence ON doc_patterns(ai_confidence);
        CREATE INDEX IF NOT EXISTS idx_doc_patterns_embedding ON doc_patterns USING ivfflat (embedding vector_cosine_ops);
    """)
    
    # Create indexes for architecture patterns
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_arch_patterns_repo_id ON arch_patterns(repo_id);
        CREATE INDEX IF NOT EXISTS idx_arch_patterns_pattern_type ON arch_patterns(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_arch_patterns_confidence ON arch_patterns(confidence);
        CREATE INDEX IF NOT EXISTS idx_arch_patterns_ai_confidence ON arch_patterns(ai_confidence);
        CREATE INDEX IF NOT EXISTS idx_arch_patterns_embedding ON arch_patterns USING ivfflat (embedding vector_cosine_ops);
    """)
    
    # Create indexes for pattern relationships
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_source ON pattern_relationships(source_pattern_id);
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_target ON pattern_relationships(target_pattern_id);
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_type ON pattern_relationships(relationship_type);
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_ai_type ON pattern_relationships(ai_relationship_type);
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_strength ON pattern_relationships(strength);
        CREATE INDEX IF NOT EXISTS idx_pattern_relationships_ai_strength ON pattern_relationships(ai_relationship_strength);
    """)
    
    # Create indexes for pattern metrics
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_pattern_id ON pattern_metrics(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_pattern_type ON pattern_metrics(pattern_type);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_complexity ON pattern_metrics(complexity_score);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_maintainability ON pattern_metrics(maintainability_score);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_reusability ON pattern_metrics(reusability_score);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_usage ON pattern_metrics(usage_count);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_ai_quality ON pattern_metrics(ai_quality_score);
        CREATE INDEX IF NOT EXISTS idx_pattern_metrics_ai_impact ON pattern_metrics(ai_impact_score);
    """)
    
    # Create indexes for pattern learning history
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pattern_learning_repo_id ON pattern_learning_history(repo_id);
        CREATE INDEX IF NOT EXISTS idx_pattern_learning_pattern_id ON pattern_learning_history(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_pattern_learning_type ON pattern_learning_history(learning_type);
        CREATE INDEX IF NOT EXISTS idx_pattern_learning_confidence ON pattern_learning_history(confidence);
        CREATE INDEX IF NOT EXISTS idx_pattern_learning_created_at ON pattern_learning_history(created_at);
    """)
    
    # Create indexes for cross-repository analysis
    await txn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cross_repo_pattern_id ON pattern_cross_repo_analysis(pattern_id);
        CREATE INDEX IF NOT EXISTS idx_cross_repo_source ON pattern_cross_repo_analysis(source_repo_id);
        CREATE INDEX IF NOT EXISTS idx_cross_repo_target ON pattern_cross_repo_analysis(target_repo_id);
        CREATE INDEX IF NOT EXISTS idx_cross_repo_similarity ON pattern_cross_repo_analysis(similarity_score);
        CREATE INDEX IF NOT EXISTS idx_cross_repo_adaptation ON pattern_cross_repo_analysis(adaptation_score);
        CREATE INDEX IF NOT EXISTS idx_cross_repo_conflict ON pattern_cross_repo_analysis(conflict_score);
    """)

class SchemaVersion:
    """Track and manage schema versions."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._current_version = None
        self._migrations = {}
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
    
    async def initialize(self):
        """Initialize schema version tracking."""
        if self._initialized:
            return
            
        async with self._lock:
            try:
                # Create schema version table if it doesn't exist
                await schema_manager._execute_query("""
                    CREATE TABLE IF NOT EXISTS schema_versions (
                        id SERIAL PRIMARY KEY,
                        version TEXT NOT NULL,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        description TEXT,
                        checksum TEXT,
                        status TEXT DEFAULT 'pending',
                        error TEXT,
                        UNIQUE(version)
                    )
                """)
                
                # Get current version
                result = await schema_manager._execute_query("""
                    SELECT version FROM schema_versions 
                    WHERE status = 'success'
                    ORDER BY applied_at DESC 
                    LIMIT 1
                """)
                
                if result:
                    self._current_version = result[0]['version']
                
                self._initialized = True
                log("Schema version tracking initialized", level="info")
            except Exception as e:
                log(f"Error initializing schema version tracking: {e}", level="error")
                raise SchemaError(f"Failed to initialize schema version tracking: {e}")
    
    def register_migration(self, version: str, up_sql: str, down_sql: str, description: str = None):
        """Register a schema migration.
        
        Args:
            version: Schema version
            up_sql: SQL to upgrade to this version
            down_sql: SQL to downgrade from this version
            description: Optional description of the migration
        """
        self._migrations[version] = {
            'up': up_sql,
            'down': down_sql,
            'description': description,
            'checksum': self._calculate_checksum(up_sql + down_sql)
        }
    
    def _calculate_checksum(self, content: str) -> str:
        """Calculate checksum for migration content."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def get_current_version(self) -> Optional[str]:
        """Get current schema version."""
        if not self._initialized:
            await self.initialize()
        return self._current_version
    
    async def get_pending_migrations(self) -> List[str]:
        """Get list of pending migrations."""
        if not self._initialized:
            await self.initialize()
            
        current = self._current_version
        pending = []
        
        for version in sorted(self._migrations.keys()):
            if not current or version > current:
                pending.append(version)
        
        return pending
    
    @handle_async_errors(error_types=(SchemaError, PostgresError))
    async def migrate_to_version(self, target_version: str) -> bool:
        """Migrate schema to target version."""
        migration_start_time = time.time()
        total_migrations = 0
        successful_migrations = 0
        failed_migrations = []
        
        if not self._initialized:
            await self.initialize()
            
        async with self._lock:
            try:
                current = await self.get_current_version()
                
                # Add health monitoring for migration status
                await global_health_monitor.update_component_status(
                    "schema_manager",
                    ComponentStatus.HEALTHY,
                    details={
                        "current_version": current,
                        "target_version": target_version,
                        "operation": "migration_started",
                        "start_time": migration_start_time
                    }
                )
                
                if current == target_version:
                    log(f"Already at version {target_version}", level="info")
                    return True
                
                if target_version not in self._migrations:
                    raise SchemaError(f"Unknown version: {target_version}")
                
                # Determine if we need to upgrade or downgrade
                upgrade = not current or target_version > current
                
                if upgrade:
                    versions = [v for v in sorted(self._migrations.keys()) 
                              if not current or v > current]
                    versions = [v for v in versions if v <= target_version]
                else:
                    versions = [v for v in sorted(self._migrations.keys(), reverse=True)
                              if v > target_version and v <= current]
                
                # Execute migrations in sequence
                async with transaction_scope() as txn:
                    for version in versions:
                        total_migrations += 1
                        migration = self._migrations[version]
                        sql = migration['up'] if upgrade else migration['down']
                        description = migration['description']
                        checksum = migration['checksum']
                        
                        step_start_time = time.time()
                        try:
                            # Update health status with progress metrics
                            await global_health_monitor.update_component_status(
                                "schema_manager",
                                ComponentStatus.HEALTHY,
                                details={
                                    "current_version": version,
                                    "operation": "migration_step",
                                    "progress": {
                                        "total_migrations": len(versions),
                                        "completed_migrations": successful_migrations,
                                        "elapsed_time": time.time() - migration_start_time,
                                        "success_rate": (successful_migrations / total_migrations) * 100 if total_migrations > 0 else 0,
                                        "remaining_migrations": len(versions) - total_migrations,
                                        "estimated_completion_time": (
                                            migration_start_time + 
                                            (time.time() - migration_start_time) * len(versions) / total_migrations
                                            if total_migrations > 0 else None
                                        )
                                    },
                                    "current_step": {
                                        "version": version,
                                        "description": description,
                                        "direction": "upgrade" if upgrade else "downgrade",
                                        "start_time": step_start_time
                                    }
                                }
                            )
                            
                            # Record migration start
                            await schema_manager._execute_query("""
                                INSERT INTO schema_versions 
                                (version, description, checksum, status)
                                VALUES ($1, $2, $3, 'pending')
                            """, (version, description, checksum))
                            
                            # Execute migration
                            await schema_manager._execute_query(sql)
                            
                            # Update migration status
                            await schema_manager._execute_query("""
                                UPDATE schema_versions 
                                SET status = 'success', 
                                    applied_at = CURRENT_TIMESTAMP
                                WHERE version = $1
                            """, (version,))
                            
                            self._current_version = version
                            successful_migrations += 1
                            
                            # Log success metrics
                            step_duration = time.time() - step_start_time
                            await log(
                                f"Migrated to version {version}",
                                level="info",
                                context={
                                    "duration": step_duration,
                                    "success_rate": (successful_migrations / total_migrations) * 100
                                }
                            )
                            
                        except Exception as e:
                            failed_migrations.append({
                                "version": version,
                                "error": str(e),
                                "step_duration": time.time() - step_start_time
                            })
                            
                            # Update health status for migration failure
                            await global_health_monitor.update_component_status(
                                "schema_manager",
                                ComponentStatus.UNHEALTHY,
                                error=True,
                                details={
                                    "failed_version": version,
                                    "error": str(e),
                                    "operation": "migration_failed",
                                    "progress": {
                                        "total_migrations": len(versions),
                                        "completed_migrations": successful_migrations,
                                        "failed_migrations": total_migrations - successful_migrations,
                                        "elapsed_time": time.time() - migration_start_time,
                                        "success_rate": (successful_migrations / total_migrations) * 100 if total_migrations > 0 else 0,
                                        "failed_steps": failed_migrations
                                    }
                                }
                            )
                            
                            # Record error for audit
                            await ErrorAudit.record_error(
                                e,
                                f"schema_migration_{version}",
                                (SchemaError, PostgresError),
                                severity=ErrorSeverity.ERROR
                            )
                            raise
                
                # Final success status update
                if successful_migrations == len(versions):
                    await global_health_monitor.update_component_status(
                        "schema_manager",
                        ComponentStatus.HEALTHY,
                        details={
                            "operation": "migration_completed",
                            "final_version": target_version,
                            "total_duration": time.time() - migration_start_time,
                            "migrations_applied": successful_migrations,
                            "success_rate": 100.0
                        }
                    )
                
                return successful_migrations == len(versions)
                
            except Exception as e:
                await log(f"Schema migration failed: {e}", level="error")
                raise SchemaError(f"Schema migration failed: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        # Cancel any pending tasks
        if self._pending_tasks:
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
        
        self._initialized = False
        self._current_version = None
        self._migrations.clear()

# Create global instance
schema_version = SchemaVersion()

# Register cleanup handler
register_shutdown_handler(schema_version.cleanup)