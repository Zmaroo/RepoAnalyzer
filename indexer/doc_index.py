import json
from db.psql import query
from utils.logger import log
from embedding.embedding_models import DocEmbedder

# Note: The create_docs_table() function has been removed.
# Table creation is now managed in db/schema.py.

doc_embedder = DocEmbedder()

def upsert_doc(repo_id: int, file_path: str, content: str, doc_type: str = 'markdown', related_code_path: str = None, metadata: dict = None):
    try:
        embedding = doc_embedder.embed(content)
        embedding_json = json.dumps(embedding.tolist() if hasattr(embedding, "tolist") else embedding)
        
        metadata = metadata or {}
        metadata.update({
            'lines_count': len(content.splitlines()),
            'char_count': len(content)
        })
        
        insert_sql = """
        INSERT INTO repo_docs 
        (repo_id, file_path, content, doc_type, related_code_path, embedding, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (repo_id, file_path) 
        DO UPDATE SET 
            content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id;
        """
        result = query(
            insert_sql, 
            (repo_id, file_path, content, doc_type, related_code_path, embedding_json, json.dumps(metadata))
        )
        return result[0]['id']
    except Exception as e:
        log(f"Error upserting doc {file_path}: {e}", level="error")
        return None

def search_docs(query_text: str, repo_id: int | None = None, limit: int = 5) -> list[dict]:
    sql = """
    SELECT id, repo_id, file_path, content
    FROM repo_docs
    WHERE content ILIKE %s
    """
    params: tuple = (f"%{query_text}%",)
    if repo_id is not None:
        sql += " AND repo_id = %s"
        params += (repo_id,)
    sql += " LIMIT %s;"
    params += (limit,)
    return query(sql, params)

def search_available_docs(search_term: str, repo_id: int | None = None, limit: int = 5) -> list[dict]:
    """
    Search for documentation that could be linked to a project.
    
    Args:
        search_term: Text to search for in documentation
        repo_id: Optional repo ID to exclude docs already linked
        limit: Maximum number of results to return
    """
    sql = """
    SELECT d.id, d.file_path, d.doc_type, d.metadata,
           array_agg(r.repo_id) as linked_repos
    FROM repo_docs d
    LEFT JOIN repo_doc_relations r ON d.id = r.doc_id
    WHERE d.content ILIKE %s
    GROUP BY d.id, d.file_path, d.doc_type, d.metadata
    LIMIT %s;
    """
    params: tuple = (f"%{search_term}%", limit)
    return query(sql, params)

def link_doc_to_repo(doc_id: int, repo_id: int, is_primary: bool = False) -> bool:
    """
    Link an existing documentation to a repository.
    
    Args:
        doc_id: ID of the documentation to link
        repo_id: ID of the repository to link to
        is_primary: Whether this is the primary repo for this doc
    """
    try:
        sql = """
        INSERT INTO repo_doc_relations (repo_id, doc_id, is_primary)
        VALUES (%s, %s, %s)
        ON CONFLICT (repo_id, doc_id) DO UPDATE
        SET is_primary = EXCLUDED.is_primary;
        """
        query(sql, (repo_id, doc_id, is_primary))
        return True
    except Exception as e:
        log(f"Error linking doc {doc_id} to repo {repo_id}: {e}", level="error")
        return False

def get_repo_docs(repo_id: int, include_shared: bool = True) -> list[dict]:
    """
    Get all documentation associated with a repository.
    
    Args:
        repo_id: ID of the repository
        include_shared: Whether to include docs shared from other repos
    """
    sql = """
    SELECT d.*, r.is_primary,
           array_agg(DISTINCT rr.repo_id) as shared_with_repos
    FROM repo_docs d
    JOIN repo_doc_relations r ON d.id = r.doc_id
    LEFT JOIN repo_doc_relations rr ON d.id = rr.doc_id
    WHERE r.repo_id = %s
    GROUP BY d.id, r.is_primary
    ORDER BY r.is_primary DESC, d.updated_at DESC;
    """
    return query(sql, (repo_id,))

def share_docs_with_repo(doc_ids: list[int], target_repo_id: int) -> dict:
    """
    Share multiple documents with a target repository.
    
    Args:
        doc_ids: List of documentation IDs to share
        target_repo_id: Repository to share with
    
    Returns:
        Dictionary with success and error counts
    """
    results = {"success": 0, "errors": 0}
    for doc_id in doc_ids:
        if link_doc_to_repo(doc_id, target_repo_id):
            results["success"] += 1
        else:
            results["errors"] += 1
    return results