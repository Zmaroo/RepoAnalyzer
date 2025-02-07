from db.psql import query
from transformers import AutoTokenizer, AutoModel
import torch
from indexer.doc_index import upsert_doc
from utils.logger import log
import redis
import json
import hashlib

_model = None
_tokenizer = None

# Connect to Redis (adjust host, port, and db if needed)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def init_model():
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
        _model = AutoModel.from_pretrained("microsoft/graphcodebert-base")

def compute_embedding(text) -> list:
    """
    Computes the embedding of the given text using the loaded model.
    Uses Redis to cache the computed embedding for future calls.
    
    If the passed text is not a string, this function will:
      - If it's a bytes object, decode it using UTF-8.
      - If it has a 'text' attribute (like a tree_sitter.Node), use that.
      - Otherwise, fallback to str(text).
    """
    # If text is of type bytes, decode it:
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except Exception:
            text = str(text)
    
    # If text is not a string, try to get a .text attribute or convert it:
    if not isinstance(text, str):
        try:
            text = text.text
        except AttributeError:
            text = str(text)
    
    key = "embedding:" + hashlib.md5(text.encode('utf-8')).hexdigest()
    cached = redis_client.get(key)
    if cached is not None:
        # Return the cached embedding (stored as a JSON string)
        embedding = json.loads(cached.decode('utf-8'))
        log(f"Loaded embedding from cache for key {key}", level="debug")
        return embedding

    # Compute embedding if not cached
    init_model()
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = _model(**inputs)
    embedding = outputs.last_hidden_state[:, 0, :].squeeze().tolist()

    # Save the computed embedding in Redis with an expiry time (e.g., one hour)
    redis_client.setex(key, 3600, json.dumps(embedding))
    log(f"Stored embedding in cache for key {key}", level="debug")
    return embedding

def to_pgvector_literal(vector_list: list) -> str:
    """
    Converts a Python list of numbers into a string literal
    accepted by PGVector. For example: [0.1, 0.2, 0.3] -> "[0.1,0.2,0.3]"
    """
    return "[" + ", ".join(map(str, vector_list)) + "]"

def upsert_code(repo_id: int, file_path: str, ast: str):
    embedding = compute_embedding(ast)
    query("""
        INSERT INTO code_snippets (repo_id, file_path, ast, embedding)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (repo_id, file_path) DO UPDATE 
        SET ast = EXCLUDED.ast, embedding = EXCLUDED.embedding;
    """, (repo_id, file_path, ast, embedding))
    log(f"Indexed code for repo_id {repo_id} at {file_path}")

def search_code(query_text: str, repo_id: int | None = None, limit: int = 5) -> list[dict]:
    """
    Searches for code snippets by computing the embedding of the query text,
    then comparing it with the stored embedding. The computed embedding is
    converted into a PGVector literal and cast explicitly in the SQL query.
    """
    query_embedding = compute_embedding(query_text)
    vector_literal = to_pgvector_literal(query_embedding)
    # Explicitly cast the submitted parameter to type 'vector'
    sql = ("SELECT id, repo_id, file_path, ast, "
           "embedding <=> %s::vector AS similarity FROM code_snippets")
    params = (vector_literal,)
    if repo_id is not None:
        sql += " WHERE repo_id = %s"
        params += (repo_id,)
    sql += " ORDER BY similarity ASC LIMIT %s;"
    params += (limit,)
    return query(sql, params)

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