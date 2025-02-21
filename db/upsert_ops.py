"""
Unified database upsert operations.
Provides a single source of truth for all database updates/inserts.
"""

import json
from typing import Dict, Optional
from db.psql import query, execute
from db.neo4j_ops import Neo4jTools, run_query
from utils.logger import log
from embedding.embedding_models import DocEmbedder
from db.transaction import transaction_scope

# Initialize Neo4j tools once
neo4j = Neo4jTools()
doc_embedder = DocEmbedder()

async def store_code_in_postgres(code_data: Dict) -> None:
    """Store code data in PostgreSQL"""
    sql = """
    INSERT INTO code_snippets (repo_id, file_path, ast, embedding, enriched_features)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (repo_id, file_path) 
    DO UPDATE SET 
        ast = EXCLUDED.ast,
        embedding = EXCLUDED.embedding,
        enriched_features = EXCLUDED.enriched_features;
    """
    await execute(sql, (
        code_data['repo_id'],
        code_data['file_path'],
        json.dumps(code_data['ast']) if code_data.get('ast') else None,
        code_data.get('embedding'),
        json.dumps(code_data['enriched_features']) if code_data.get('enriched_features') else None
    ))

async def store_code_in_neo4j(code_data: Dict) -> None:
    """Store code data in Neo4j"""
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
    run_query(cypher, {'repo_id': code_data['repo_id'], 
                      'file_path': code_data['file_path'], 
                      'properties': properties})

async def store_doc_in_postgres(doc_data: Dict) -> int:
    """Store document data in PostgreSQL and return doc_id"""
    sql = """
    INSERT INTO repo_docs (file_path, content, doc_type, version, cluster_id, 
                          related_code_path, embedding, metadata, quality_metrics)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    RETURNING id;
    """
    result = await query(sql, (
        doc_data['file_path'],
        doc_data['content'],
        doc_data.get('doc_type', 'markdown'),
        doc_data.get('version', 1),
        doc_data.get('cluster_id'),
        doc_data.get('related_code_path'),
        doc_data.get('embedding'),
        json.dumps(doc_data.get('metadata', {})),
        json.dumps(doc_data.get('quality_metrics', {}))
    ))
    
    doc_id = result[0]['id']

    # Create relation
    relation_sql = """
    INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
    VALUES ($1, $2, $3)
    ON CONFLICT (repo_id, doc_id) DO UPDATE
    SET is_primary = EXCLUDED.is_primary;
    """
    await execute(relation_sql, (
        doc_data['repo_id'],
        doc_id,
        doc_data.get('is_primary', False)
    ))
    
    return doc_id

async def store_doc_in_neo4j(doc_data: Dict) -> None:
    """Store document data in Neo4j"""
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
    run_query(cypher, {'repo_id': doc_data['repo_id'], 
                      'path': doc_data['file_path'], 
                      'properties': properties})

async def upsert_code_snippet(code_data: Dict) -> None:
    """Store code data with transaction coordination."""
    async with transaction_scope() as txn:
        # PostgreSQL storage
        sql = """
        INSERT INTO code_snippets (repo_id, file_path, ast, embedding, enriched_features)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (repo_id, file_path) 
        DO UPDATE SET 
            ast = EXCLUDED.ast,
            embedding = EXCLUDED.embedding,
            enriched_features = EXCLUDED.enriched_features;
        """
        await execute(sql, (
            code_data['repo_id'],
            code_data['file_path'],
            code_data.get('ast'),
            code_data.get('embedding'),
            code_data.get('enriched_features')
        ))
        
        # Neo4j storage
        if code_data.get('ast'):
            await neo4j.store_code_node(code_data)

async def upsert_doc(
    repo_id: int,
    file_path: str,
    content: str,
    doc_type: str,
    metadata: Optional[Dict] = None,
    is_primary: bool = True
) -> None:
    """Store documentation with transaction coordination."""
    async with transaction_scope() as txn:
        # Generate embedding
        embedding = await doc_embedder.embed_async(content)
        
        # PostgreSQL storage
        sql = """
        INSERT INTO repo_docs (repo_id, file_path, content, doc_type, metadata, embedding)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (repo_id, file_path) 
        DO UPDATE SET
            content = EXCLUDED.content,
            doc_type = EXCLUDED.doc_type,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding;
        """
        await execute(sql, (repo_id, file_path, content, doc_type, metadata, embedding))

async def upsert_repository(repo_data: Dict) -> int:
    """Store repository with transaction coordination."""
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
        result = await query(sql, (
            repo_data['repo_name'],
            repo_data.get('source_url'),
            repo_data.get('repo_type', 'active'),
            repo_data.get('active_repo_id')
        ))
        
        repo_id = result[0]['id']
        log(f"Upserted repository {repo_data['repo_name']}", level="info")
        return repo_id

async def share_docs_with_repo(doc_ids: list, target_repo_id: int) -> dict:
    """Share documents with another repository"""
    try:
        for doc_id in doc_ids:
            await execute("""
                INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
                VALUES ($1, $2, false)
                ON CONFLICT (repo_id, doc_id) DO NOTHING
            """, (target_repo_id, doc_id))
        return {"shared_docs": len(doc_ids), "target_repo": target_repo_id}
    except Exception as e:
        log(f"Error sharing docs: {e}", level="error")
        raise 