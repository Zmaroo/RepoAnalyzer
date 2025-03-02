"""[6.5] Unified database upsert operations.

Flow:
1. Storage Operations:
   - Code storage (PostgreSQL + Neo4j)
   - Documentation storage (PostgreSQL)
   - Repository metadata
   - Document sharing

2. Integration Points:
   - FileProcessor [2.0]: File content storage
   - SearchEngine [5.0]: Embedding storage
   - GraphSync [6.3]: Graph updates
   - Transaction [6.4]: Operation coordination

3. Data Flow:
   - Content validation
   - Embedding generation
   - Transaction coordination
   - Cache invalidation
"""
import json
from typing import Dict, Optional, List
from db.psql import query, execute
from db.connection import driver
from db.graph_sync import graph_sync
from utils.logger import log
from embedding.embedding_models import DocEmbedder
from db.neo4j_ops import Neo4jTools, run_query
from db.transaction import transaction_scope
from parsers.types import ParserResult, ExtractedFeatures
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.error_handling import AsyncErrorBoundary, ProcessingError, DatabaseError, PostgresError, Neo4jError, TransactionError, handle_async_errors, ErrorBoundary
neo4j = Neo4jTools()
doc_embedder = DocEmbedder()
_retry_manager = DatabaseRetryManager(RetryConfig(max_retries=5))


@handle_async_errors(error_types=(PostgresError, DatabaseError))
async def store_code_in_postgres(code_data: Dict) ->None:
    """[6.5.1] Store code data in PostgreSQL."""
    sql = """
    INSERT INTO code_snippets (repo_id, file_path, ast, embedding, enriched_features)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (repo_id, file_path) 
    DO UPDATE SET 
        ast = EXCLUDED.ast,
        embedding = EXCLUDED.embedding,
        enriched_features = EXCLUDED.enriched_features;
    """

    async def _do_store():
        await execute(sql, (code_data['repo_id'], code_data['file_path'], 
            json.dumps(code_data['ast']) if code_data.get('ast') else None,
            code_data.get('embedding'), json.dumps(code_data[
            'enriched_features']) if code_data.get('enriched_features') else
            None))
    await _retry_manager.execute_with_retry(_do_store)


@handle_async_errors(error_types=(Neo4jError, DatabaseError))
async def store_code_in_neo4j(code_data: Dict) ->None:
    """Store code data in Neo4j"""
    cypher = """
    MERGE (c:Code {repo_id: $repo_id, file_path: $file_path})
    SET c += $properties,
        c.updated_at = timestamp()
    """
    properties = {'repo_id': code_data['repo_id'], 'file_path': code_data[
        'file_path'], 'ast': code_data.get('ast'), 'embedding': code_data.
        get('embedding'), 'enriched_features': code_data.get(
        'enriched_features')}

    async def _do_store_neo4j():
        run_query(cypher, {'repo_id': code_data['repo_id'], 'file_path':
            code_data['file_path'], 'properties': properties})
    await _retry_manager.execute_with_retry(_do_store_neo4j)


@handle_async_errors(error_types=(Exception,))
async def store_doc_in_postgres(doc_data: Dict) ->int:
    """Store document data in PostgreSQL and return doc_id"""
    sql = """
    INSERT INTO repo_docs (file_path, content, doc_type, version, cluster_id, 
                          related_code_path, embedding, metadata, quality_metrics)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    RETURNING id;
    """
    result = await query(sql, (doc_data['file_path'], doc_data['content'],
        doc_data.get('doc_type', 'markdown'), doc_data.get('version', 1),
        doc_data.get('cluster_id'), doc_data.get('related_code_path'),
        doc_data.get('embedding'), json.dumps(doc_data.get('metadata', {})),
        json.dumps(doc_data.get('quality_metrics', {}))))
    doc_id = result[0]['id']
    relation_sql = """
    INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
    VALUES ($1, $2, $3)
    ON CONFLICT (repo_id, doc_id) DO UPDATE
    SET is_primary = EXCLUDED.is_primary;
    """
    await execute(relation_sql, (doc_data['repo_id'], doc_id, doc_data.get(
        'is_primary', False)))
    return doc_id


@handle_async_errors(error_types=(Neo4jError, DatabaseError))
async def store_doc_in_neo4j(doc_data: Dict) ->None:
    """Store document data in Neo4j."""
    try:
        with AsyncErrorBoundary(operation_name=
            f"Storing document {doc_data.get('file_path', 'unknown')} in Neo4j"
            , error_types=(Neo4jError, DatabaseError, Exception)
            ) as error_boundary:

            async def _do_store_neo4j():
                cypher = """
                MERGE (d:Documentation {repo_id: $repo_id, path: $path})
                SET d += $properties
                """
                properties = {'repo_id': doc_data['repo_id'], 'path':
                    doc_data['file_path'], 'content': doc_data['content'],
                    'type': doc_data.get('doc_type', 'markdown'), 'version':
                    doc_data.get('version', 1), 'cluster_id': doc_data.get(
                    'cluster_id'), 'metadata': doc_data.get('metadata', {})}
                await run_query(cypher, {'repo_id': doc_data['repo_id'],
                    'path': doc_data['file_path'], 'properties': properties})
            await _retry_manager.execute_with_retry(_do_store_neo4j)
    except Exception as e:
        log('Failed to store document in Neo4j', level='error', context={
            'operation': 'store_doc_in_neo4j', 'repo_id': doc_data.get(
            'repo_id'), 'file_path': doc_data.get('file_path'), 'error':
            str(e)})
        raise


@handle_async_errors(error_types=(PostgresError, Neo4jError, TransactionError))
async def upsert_code_snippet(code_data: Dict) ->None:
    """[6.5.2] Store code with transaction coordination."""
    async with AsyncErrorBoundary(operation_name='code upsert', error_types
        =(PostgresError, Neo4jError)):
        async with transaction_scope() as txn:
            try:
                await store_code_in_postgres(code_data)
                if code_data.get('ast'):
                    await neo4j.store_code_node(code_data)
            except Exception as e:
                log('Failed to upsert code', level='error', context={
                    'operation': 'upsert_code_snippet', 'repo_id':
                    code_data.get('repo_id'), 'file_path': code_data.get(
                    'file_path'), 'error': str(e)})
                raise


@handle_async_errors(error_types=(Neo4jError, DatabaseError))
async def upsert_doc(repo_id: int, file_path: str, content: str, doc_type:
    str, metadata: Optional[Dict]=None, is_primary: bool=True) ->Optional[str]:
    """High-level document upsert function."""
    with AsyncErrorBoundary(operation_name=
        f'Upserting document {file_path}', error_types=(Neo4jError,
        DatabaseError, Exception)):

        async def _do_upsert():
            doc_data = {'repo_id': repo_id, 'file_path': file_path,
                'content': content, 'doc_type': doc_type, 'metadata': 
                metadata or {}, 'is_primary': is_primary}
            return await neo4j.create_or_update_node(labels=['Document'],
                properties=doc_data, key_fields=['repo_id', 'file_path'])
        result = await _do_upsert()
        if result is None:
            log(f'Error upserting document: {file_path}', level='error')
            return None
        else:
            log(f'Upserted document {file_path}', level='info')
            return result

@handle_async_errors(error_types=(Exception,))

async def upsert_repository(repo_data: Dict) ->int:
    """[6.5.4] Store repository with transaction coordination."""
    async with transaction_scope() as txn:
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
        result = await query(sql, (repo_data['repo_name'], repo_data.get(
            'source_url'), repo_data.get('repo_type', 'active'), repo_data.
            get('active_repo_id')))
        repo_id = result[0]['id']
        log(f"Upserted repository {repo_data['repo_name']}", level='info')
        return repo_id


@handle_async_errors(error_types=(PostgresError, DatabaseError))
async def share_docs_with_repo(doc_ids: list, target_repo_id: int) ->dict:
    """[6.5.5] Share documents with another repository."""
    with AsyncErrorBoundary(operation_name=
        f'Sharing docs with repo {target_repo_id}', error_types=(
        PostgresError, DatabaseError, Exception)):

        async def _do_share():
            for doc_id in doc_ids:
                await execute(
                    """
                    INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
                    VALUES ($1, $2, false)
                    ON CONFLICT (repo_id, doc_id) DO NOTHING
                """
                    , (target_repo_id, doc_id))
            return {'shared_docs': len(doc_ids), 'target_repo': target_repo_id}
        result = await _do_share()
        if result is None:
            log(f'Error sharing docs: {target_repo_id}', level='error')
            raise DatabaseError(
                f'Failed to share docs with repo {target_repo_id}')
        else:
            log(f"Shared {result['shared_docs']} docs with repo {target_repo_id}"
                , level='info')
            return result
@handle_async_errors(error_types=(Exception,))


async def store_parsed_content(repo_id: int, file_path: str, ast: dict,
    features: ExtractedFeatures) ->None:
    """Store parsed content based on extracted features."""
    async with transaction_scope() as txn:
        await store_code_in_postgres(repo_id, file_path, ast, features)
        if features.has_documentation_content():
            await store_doc_in_postgres(repo_id, file_path, features)
        await neo4j.store_node_with_features(repo_id, file_path, ast, features)
