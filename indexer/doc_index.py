import json
from db.psql import query
from utils.logger import log
from embedding.embedding_models import DocEmbedder

# Note: The create_docs_table() function has been removed.
# Table creation is now managed in db/schema.py.

doc_embedder = DocEmbedder()

def upsert_doc(repo_id: int, file_path: str, content: str):
    # Compute the documentation embedding using our dedicated DocEmbedder.
    embedding = doc_embedder.embed(content)
    # Convert the embedding to JSON format (or another format your DB supports).
    # Depending on the model and downstream requirements, you may want to store as a JSON string.
    embedding_json = json.dumps(embedding.tolist() if hasattr(embedding, "tolist") else embedding)
    
    find_sql = "SELECT id FROM repo_docs WHERE repo_id = %s AND file_path = %s;"
    result = query(find_sql, (repo_id, file_path))
    if result:
        update_sql = "UPDATE repo_docs SET content = %s, embedding = %s WHERE repo_id = %s AND file_path = %s;"
        query(update_sql, (content, embedding_json, repo_id, file_path))
        log(f"Updated doc for [{repo_id}] {file_path}")
    else:
        insert_sql = """
        INSERT INTO repo_docs (repo_id, file_path, content, embedding)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """
        result = query(insert_sql, (repo_id, file_path, content, embedding_json))
        log(f"Inserted doc with id {result[0]['id']} for [{repo_id}] {file_path}")

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