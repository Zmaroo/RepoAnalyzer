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
from typing import Dict, Optional, Set, List
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    ProcessingError,
    DatabaseError,
    PostgresError,
    Neo4jError,
    TransactionError,
    handle_async_errors,
    ErrorBoundary,
    ErrorSeverity
)
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.async_runner import submit_async_task
from db.connection import connection_manager
from db.transaction import transaction_scope
from parsers.types import ParserResult, ExtractedFeatures
from embedding.embedding_models import DocEmbedder

# Initialize retry manager for upsert operations
_retry_manager = DatabaseRetryManager(RetryConfig(max_retries=5))  # More retries for upsert operations

class UpsertCoordinator:
    """Coordinates upsert operations across databases."""
    
    def __init__(self):
        self._pending_tasks: Set[asyncio.Future] = set()
        self._lock = asyncio.Lock()
        self.doc_embedder = DocEmbedder()
    
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
                
                future = submit_async_task(conn.execute(sql, (
                    code_data['repo_id'],
                    code_data['file_path'],
                    json.dumps(code_data['ast']) if code_data.get('ast') else None,
                    code_data.get('embedding'),
                    json.dumps(code_data['enriched_features']) if code_data.get('enriched_features') else None
                )))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
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
            
            future = submit_async_task(session.run(cypher, {
                'repo_id': code_data['repo_id'], 
                'file_path': code_data['file_path'], 
                'properties': properties
            }))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
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
                
                future = submit_async_task(conn.fetchrow(sql, (
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
                self._pending_tasks.add(future)
                try:
                    result = await asyncio.wrap_future(future)
                    doc_id = result['id']
                finally:
                    self._pending_tasks.remove(future)
                
                # Create relation
                relation_sql = """
                INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
                VALUES ($1, $2, $3)
                ON CONFLICT (repo_id, doc_id) DO UPDATE
                SET is_primary = EXCLUDED.is_primary;
                """
                
                future = submit_async_task(conn.execute(relation_sql, (
                    doc_data['repo_id'],
                    doc_id,
                    doc_data.get('is_primary', False)
                )))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
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
            
            future = submit_async_task(session.run(cypher, {
                'repo_id': doc_data['repo_id'], 
                'path': doc_data['file_path'],
                'properties': properties
            }))
            self._pending_tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
        finally:
            await session.close()
    
    @handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError))
    async def upsert_code_snippet(self, code_data: Dict) -> None:
        """[6.5.2] Store code with transaction coordination."""
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
        async with AsyncErrorBoundary("doc upsert", error_types=(PostgresError, Neo4jError), severity=ErrorSeverity.ERROR):
            async with transaction_scope() as txn:
                await txn.track_repo_change(repo_id)
                
                # Generate embedding if needed
                embedding = None
                if doc_type in ['markdown', 'docstring']:
                    embedding = await self.doc_embedder.embed_text(content)
                
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
            from db.graph_sync import get_graph_sync
            graph_sync = await get_graph_sync()
            await graph_sync.ensure_projection(repo_id)
    
    async def cleanup(self) -> None:
        """Clean up any pending tasks."""
        if self._pending_tasks:
            await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
            self._pending_tasks.clear()

# Create global coordinator instance
coordinator = UpsertCoordinator() 