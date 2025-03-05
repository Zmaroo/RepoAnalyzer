"""[6.5] Unified database upsert operations.

This module provides centralized upsert operations across multiple databases:
1. Code storage (PostgreSQL + Neo4j)
2. Documentation storage (PostgreSQL)
3. Repository metadata
4. Document sharing

All database operations use the centralized connection manager and transaction coordinator.
"""

import json
import asyncio
from typing import Dict, Optional, Set, List, Any
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    ProcessingError,
    DatabaseError,
    PostgresError,
    Neo4jError,
    TransactionError,
    handle_async_errors,
    ErrorSeverity
)
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from db.connection import connection_manager
from db.transaction import transaction_scope
from parsers.types import ParserResult, ExtractedFeatures
from embedding.embedding_models import doc_embedder
from utils.shutdown import register_shutdown_handler
from db.graph_sync import get_graph_sync
from db.neo4j_ops import get_neo4j_ops

# Initialize retry manager for upsert operations
_retry_manager = DatabaseRetryManager(RetryConfig(max_retries=5))  # More retries for upsert operations

class UpsertCoordinator:
    """Coordinates upsert operations across databases."""
    
    def __init__(self):
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._initialized = False
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize the upsert coordinator."""
        if not self._initialized:
            try:
                # Any coordinator-specific initialization can go here
                self._initialized = True
                log("Upsert coordinator initialized", level="info")
            except Exception as e:
                log(f"Error initializing upsert coordinator: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=[PostgresError, DatabaseError])
    async def store_code_in_postgres(self, code_data: Dict) -> None:
        """Store code data in PostgreSQL."""
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                sql = """
                INSERT INTO code_snippets (repo_id, file_path, ast, embedding, enriched_features)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (repo_id, file_path) 
                DO UPDATE SET 
                    ast = EXCLUDED.ast,
                    embedding = EXCLUDED.embedding,
                    enriched_features = EXCLUDED.enriched_features;
                """
                
                task = asyncio.create_task(conn.execute(sql, (
                    code_data['repo_id'],
                    code_data['file_path'],
                    json.dumps(code_data['ast']) if code_data.get('ast') else None,
                    code_data.get('embedding'),
                    json.dumps(code_data['enriched_features']) if code_data.get('enriched_features') else None
                )))
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    @handle_async_errors(error_types=[Neo4jError, DatabaseError])
    async def store_code_in_neo4j(self, code_data: Dict) -> None:
        """Store code data in Neo4j."""
        session = await connection_manager.get_session()
        try:
            cypher = """
            MERGE (c:Code {repo_id: $repo_id, file_path: $file_path})
            SET c += $properties,
                c.updated_at = timestamp()
            """
            properties = {
                'repo_id': code_data['repo_id'],
                'file_path': code_data['file_path'],
                'ast': code_data.get('ast'),
                'embedding': code_data.get('embedding'),
                'enriched_features': code_data.get('enriched_features')
            }
            
            task = asyncio.create_task(session.run(cypher, {
                'repo_id': code_data['repo_id'], 
                'file_path': code_data['file_path'], 
                'properties': properties
            }))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=[PostgresError, DatabaseError])
    async def store_doc_in_postgres(self, doc_data: Dict) -> int:
        """Store document data in PostgreSQL and return doc_id."""
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                # Store document
                sql = """
                INSERT INTO repo_docs (file_path, content, doc_type, version, cluster_id, 
                                    related_code_path, embedding, metadata, quality_metrics)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id;
                """
                
                task = asyncio.create_task(conn.fetchrow(sql, (
                    doc_data['file_path'],
                    doc_data['content'],
                    doc_data.get('doc_type', 'markdown'),
                    doc_data.get('version', 1),
                    doc_data.get('cluster_id'),
                    doc_data.get('related_code_path'),
                    doc_data.get('embedding'),
                    json.dumps(doc_data.get('metadata', {})),
                    json.dumps(doc_data.get('quality_metrics', {}))
                )))
                self._pending_tasks.add(task)
                try:
                    result = await task
                    doc_id = result['id']
                finally:
                    self._pending_tasks.remove(task)
                
                # Create relation
                relation_sql = """
                INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
                VALUES ($1, $2, $3)
                ON CONFLICT (repo_id, doc_id) DO UPDATE
                SET is_primary = EXCLUDED.is_primary;
                """
                
                task = asyncio.create_task(conn.execute(relation_sql, (
                    doc_data['repo_id'],
                    doc_id,
                    doc_data.get('is_primary', False)
                )))
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
                
                return doc_id
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    @handle_async_errors(error_types=[Neo4jError, DatabaseError])
    async def store_doc_in_neo4j(self, doc_data: Dict) -> None:
        """Store document data in Neo4j."""
        session = await connection_manager.get_session()
        try:
            cypher = """
            MERGE (d:Documentation {repo_id: $repo_id, path: $path})
            SET d += $properties
            """
            properties = {
                'repo_id': doc_data['repo_id'],
                'path': doc_data['file_path'],
                'content': doc_data['content'],
                'type': doc_data.get('doc_type', 'markdown'),
                'version': doc_data.get('version', 1),
                'cluster_id': doc_data.get('cluster_id'),
                'metadata': doc_data.get('metadata', {})
            }
            
            task = asyncio.create_task(session.run(cypher, {
                'repo_id': doc_data['repo_id'], 
                'path': doc_data['file_path'],
                'properties': properties
            }))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError))
    async def upsert_code_snippet(self, code_data: Dict) -> None:
        """[6.5.2] Store code with transaction coordination."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("code upsert", error_types=(PostgresError, Neo4jError), severity=ErrorSeverity.ERROR):
            async with transaction_scope() as txn:
                await txn.track_repo_change(code_data['repo_id'])
                await self.store_code_in_postgres(code_data)
                
                if code_data.get('ast'):
                    await self.store_code_in_neo4j(code_data)
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError))
    async def upsert_doc(
        self,
        repo_id: int,
        file_path: str, 
        content: str,
        doc_type: str,
        metadata: Optional[Dict] = None,
        is_primary: bool = True
    ) -> Optional[int]:
        """[6.5.3] Store document with transaction coordination."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("doc upsert", error_types=(PostgresError, Neo4jError), severity=ErrorSeverity.ERROR):
            async with transaction_scope() as txn:
                await txn.track_repo_change(repo_id)
                
                # Generate embedding if needed
                embedding = None
                if doc_type in ['markdown', 'docstring']:
                    embedding = await doc_embedder.embed_text(content)
                
                doc_data = {
                    'repo_id': repo_id,
                    'file_path': file_path,
                    'content': content,
                    'doc_type': doc_type,
                    'metadata': metadata or {},
                    'is_primary': is_primary,
                    'embedding': embedding
                }
                
                doc_id = await self.store_doc_in_postgres(doc_data)
                await self.store_doc_in_neo4j(doc_data)
                return doc_id
    
    @handle_async_errors(error_types=(PostgresError, TransactionError))
    async def upsert_repository(self, repo_data: Dict) -> int:
        """[6.5.4] Store repository with transaction coordination."""
        if not self._initialized:
            await self.initialize()
            
        async with transaction_scope() as txn:
            conn = await connection_manager.get_postgres_connection()
            try:
                async with conn.transaction():
                    sql = """
                    INSERT INTO repositories (repo_name, source_url, repo_type, active_repo_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (repo_name) 
                    DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        repo_type = EXCLUDED.repo_type,
                        active_repo_id = EXCLUDED.active_repo_id,
                        last_updated = CURRENT_TIMESTAMP
                    RETURNING id;
                    """
                    
                    future = submit_async_task(conn.fetchrow(sql, (
                        repo_data['repo_name'],
                        repo_data.get('source_url'),
                        repo_data.get('repo_type', 'active'),
                        repo_data.get('active_repo_id')
                    )))
                    self._pending_tasks.add(future)
                    try:
                        result = await asyncio.wrap_future(future)
                        repo_id = result['id']
                        await txn.track_repo_change(repo_id)
                        log(f"Upserted repository {repo_data['repo_name']}", level="info")
                        return repo_id
                    finally:
                        self._pending_tasks.remove(future)
            finally:
                await connection_manager.release_postgres_connection(conn)
    
    @handle_async_errors(error_types=[PostgresError, DatabaseError])
    async def share_docs_with_repo(self, doc_ids: List[int], target_repo_id: int) -> Dict:
        """[6.5.5] Share documents with another repository."""
        if not self._initialized:
            await self.initialize()
            
        async with transaction_scope() as txn:
            conn = await connection_manager.get_postgres_connection()
            try:
                async with conn.transaction():
                    sql = """
                    INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
                    SELECT $1, doc_id, false
                    FROM repo_doc_relations
                    WHERE doc_id = ANY($2)
                    ON CONFLICT (repo_id, doc_id) DO NOTHING
                    RETURNING doc_id;
                    """
                    
                    future = submit_async_task(conn.fetch(sql, (target_repo_id, doc_ids)))
                    self._pending_tasks.add(future)
                    try:
                        result = await asyncio.wrap_future(future)
                        shared_count = len(result)
                        await txn.track_repo_change(target_repo_id)
                        return {
                            'shared_count': shared_count,
                            'target_repo_id': target_repo_id,
                            'doc_ids': [r['doc_id'] for r in result]
                        }
                    finally:
                        self._pending_tasks.remove(future)
            finally:
                await connection_manager.release_postgres_connection(conn)
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError))
    async def store_parsed_content(
        self,
        repo_id: int,
        file_path: str, 
        ast: dict,
        features: ExtractedFeatures
    ) -> None:
        """[6.5.6] Store parsed content with transaction coordination."""
        if not self._initialized:
            await self.initialize()
            
        async with transaction_scope() as txn:
            await txn.track_repo_change(repo_id)
            
            # Store in PostgreSQL
            await self.store_code_in_postgres({
                'repo_id': repo_id,
                'file_path': file_path,
                'ast': ast,
                'enriched_features': features.to_dict()
            })
            
            # Store in Neo4j
            await self.store_code_in_neo4j({
                'repo_id': repo_id,
                'file_path': file_path,
                'ast': ast,
                'enriched_features': features.to_dict()
            })
            
            # Get graph sync instance
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
    
    @handle_async_errors(error_types=DatabaseError)
    async def upsert_pattern(
        self,
        pattern_data: Dict[str, Any],
        repo_id: int,
        pattern_type: str,
        transaction: Optional[Transaction] = None
    ) -> int:
        """Upsert a pattern with AI enhancements."""
        async with self._get_transaction(transaction) as txn:
            # Prepare base pattern data
            pattern_values = {
                "repo_id": repo_id,
                "pattern_type": pattern_type,
                "language": pattern_data.get("language"),
                "content": pattern_data.get("content"),
                "confidence": pattern_data.get("confidence", 0.7),
                "complexity": pattern_data.get("complexity"),
                "dependencies": pattern_data.get("dependencies", []),
                "documentation": pattern_data.get("documentation"),
                "metadata": pattern_data.get("metadata", {}),
                "embedding": pattern_data.get("embedding"),
                "ai_insights": pattern_data.get("ai_insights", {}),
                "ai_confidence": pattern_data.get("ai_confidence"),
                "ai_metrics": pattern_data.get("ai_metrics", {}),
                "ai_recommendations": pattern_data.get("ai_recommendations", {}),
                "updated_at": "CURRENT_TIMESTAMP"
            }
            
            # Upsert pattern
            query = """
            INSERT INTO code_patterns (
                repo_id, pattern_type, language, content, confidence,
                complexity, dependencies, documentation, metadata,
                embedding, ai_insights, ai_confidence, ai_metrics,
                ai_recommendations, updated_at
            )
            VALUES (
                :repo_id, :pattern_type, :language, :content, :confidence,
                :complexity, :dependencies, :documentation, :metadata,
                :embedding, :ai_insights, :ai_confidence, :ai_metrics,
                :ai_recommendations, :updated_at
            )
            ON CONFLICT (repo_id, pattern_type, language, content)
            DO UPDATE SET
                confidence = EXCLUDED.confidence,
                complexity = EXCLUDED.complexity,
                dependencies = EXCLUDED.dependencies,
                documentation = EXCLUDED.documentation,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                ai_insights = EXCLUDED.ai_insights,
                ai_confidence = EXCLUDED.ai_confidence,
                ai_metrics = EXCLUDED.ai_metrics,
                ai_recommendations = EXCLUDED.ai_recommendations,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """
            
            result = await txn.execute(query, pattern_values)
            pattern_id = result[0][0]
            
            # Store pattern metrics
            if pattern_data.get("metrics"):
                await self._store_pattern_metrics(pattern_id, pattern_data["metrics"], txn)
            
            # Store pattern relationships
            if pattern_data.get("relationships"):
                await self._store_pattern_relationships(pattern_id, pattern_data["relationships"], txn)
            
            # Store in Neo4j
            await self._store_in_neo4j(pattern_id, pattern_data, txn)
            
            return pattern_id

    async def _store_pattern_metrics(
        self,
        pattern_id: int,
        metrics: Dict[str, Any],
        transaction: Transaction
    ) -> None:
        """Store pattern metrics with AI enhancements."""
        query = """
        INSERT INTO pattern_metrics (
            pattern_id, pattern_type, complexity_score,
            maintainability_score, reusability_score,
            usage_count, last_used, metadata,
            ai_quality_score, ai_impact_score,
            ai_trend_analysis, ai_recommendations
        )
        VALUES (
            :pattern_id, :pattern_type, :complexity_score,
            :maintainability_score, :reusability_score,
            :usage_count, :last_used, :metadata,
            :ai_quality_score, :ai_impact_score,
            :ai_trend_analysis, :ai_recommendations
        )
        ON CONFLICT (pattern_id, pattern_type)
        DO UPDATE SET
            complexity_score = EXCLUDED.complexity_score,
            maintainability_score = EXCLUDED.maintainability_score,
            reusability_score = EXCLUDED.reusability_score,
            usage_count = pattern_metrics.usage_count + 1,
            last_used = CURRENT_TIMESTAMP,
            metadata = EXCLUDED.metadata,
            ai_quality_score = EXCLUDED.ai_quality_score,
            ai_impact_score = EXCLUDED.ai_impact_score,
            ai_trend_analysis = EXCLUDED.ai_trend_analysis,
            ai_recommendations = EXCLUDED.ai_recommendations
        """
        
        values = {
            "pattern_id": pattern_id,
            "pattern_type": metrics.get("pattern_type"),
            "complexity_score": metrics.get("complexity_score"),
            "maintainability_score": metrics.get("maintainability_score"),
            "reusability_score": metrics.get("reusability_score"),
            "usage_count": metrics.get("usage_count", 1),
            "last_used": "CURRENT_TIMESTAMP",
            "metadata": metrics.get("metadata", {}),
            "ai_quality_score": metrics.get("ai_quality_score"),
            "ai_impact_score": metrics.get("ai_impact_score"),
            "ai_trend_analysis": metrics.get("ai_trend_analysis", {}),
            "ai_recommendations": metrics.get("ai_recommendations", {})
        }
        
        await transaction.execute(query, values)

    async def _store_pattern_relationships(
        self,
        pattern_id: int,
        relationships: List[Dict[str, Any]],
        transaction: Transaction
    ) -> None:
        """Store pattern relationships with AI insights."""
        query = """
        INSERT INTO pattern_relationships (
            source_pattern_id, target_pattern_id,
            relationship_type, strength, metadata,
            ai_relationship_type, ai_relationship_strength,
            ai_insights
        )
        VALUES (
            :source_pattern_id, :target_pattern_id,
            :relationship_type, :strength, :metadata,
            :ai_relationship_type, :ai_relationship_strength,
            :ai_insights
        )
        ON CONFLICT (source_pattern_id, target_pattern_id, relationship_type)
        DO UPDATE SET
            strength = EXCLUDED.strength,
            metadata = EXCLUDED.metadata,
            ai_relationship_type = EXCLUDED.ai_relationship_type,
            ai_relationship_strength = EXCLUDED.ai_relationship_strength,
            ai_insights = EXCLUDED.ai_insights,
            updated_at = CURRENT_TIMESTAMP
        """
        
        for rel in relationships:
            values = {
                "source_pattern_id": pattern_id,
                "target_pattern_id": rel["target_id"],
                "relationship_type": rel["type"],
                "strength": rel.get("strength", 0.5),
                "metadata": rel.get("metadata", {}),
                "ai_relationship_type": rel.get("ai_relationship_type"),
                "ai_relationship_strength": rel.get("ai_relationship_strength"),
                "ai_insights": rel.get("ai_insights", {})
            }
            
            await transaction.execute(query, values)

    async def _store_in_neo4j(
        self,
        pattern_id: int,
        pattern_data: Dict[str, Any],
        transaction: Transaction
    ) -> None:
        """Store pattern in Neo4j with AI enhancements."""
        neo4j_ops = await get_neo4j_ops()
        
        # Store pattern node
        await neo4j_ops.store_pattern_node(pattern_data)
        
        # Store relationships if available
        if pattern_data.get("relationships"):
            await neo4j_ops.store_pattern_relationships(pattern_id, pattern_data["relationships"])
        
        # Ensure graph projections are updated
        graph_sync = await get_graph_sync()
        await graph_sync.ensure_pattern_projection(pattern_data["repo_id"])
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Upsert coordinator cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up upsert coordinator: {e}", level="error")

# Create global coordinator instance
coordinator = UpsertCoordinator()

# Register cleanup handler
async def cleanup_upsert():
    """Cleanup upsert coordinator resources."""
    try:
        await coordinator.cleanup()
        log("Upsert coordinator resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up upsert coordinator resources: {e}", level="error")

register_shutdown_handler(cleanup_upsert) 