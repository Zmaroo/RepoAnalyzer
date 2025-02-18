from db.psql import query
from transformers import AutoTokenizer, AutoModel
import torch
from indexer.doc_index import upsert_doc
from utils.logger import log
import json
import hashlib
from embedding.embedding_models import CodeEmbedder
from utils.cache import cache  # Use our unified cache

_model = None
_tokenizer = None

# Initialize the code embedder once.
code_embedder = CodeEmbedder()

def init_model():
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
        _model = AutoModel.from_pretrained("microsoft/graphcodebert-base")

def compute_embedding(text) -> list:
    """
    Computes the embedding of the given text using the loaded model.
    Uses the unified cache to store/retrieve the computed embedding for future calls.
    
    If the passed text is not a string, this function will:
      - If it's a bytes object, decode it using UTF-8.
      - If it has a 'text' attribute (like a tree_sitter.Node), use that.
      - Otherwise, fallback to str(text).
    """
    # Ensure text is a string.
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except Exception:
            text = str(text)
    if not isinstance(text, str):
        try:
            text = text.text
        except AttributeError:
            text = str(text)
    
    # Create a cache key based on MD5 hash of the text.
    key = "embedding:" + hashlib.md5(text.encode('utf-8')).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        try:
            embedding = json.loads(cached)
            log(f"Loaded embedding from cache for key {key}", level="debug")
            return embedding
        except Exception:
            pass  # If deserialization fails, continue to compute.
    
    # Compute embedding if not cached.
    init_model()
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    # Ensure inputs are on the proper device.
    inputs = inputs.to(_model.device)
    with torch.no_grad():
        outputs = _model(**inputs)
    embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().tolist()
    
    # Save the computed embedding in cache (expire in 3600 seconds).
    try:
        cache.set(key, json.dumps(embedding), ex=3600)
        log(f"Stored embedding in cache for key {key}", level="debug")
    except Exception as e:
        log(f"Error caching embedding: {e}", level="warning")
    return embedding

def to_pgvector_literal(vector_list: list) -> str:
    """
    Converts a Python list of numbers into a string literal
    accepted by PGVector. For example: [0.1, 0.2, 0.3] -> "[0.1,0.2,0.3]"
    """
    return "[" + ", ".join(map(str, vector_list)) + "]"

def upsert_code(repo_id: int, file_path: str, ast, embedding=None):
    """
    Upsert code snippet information into the Postgres database.
    The AST is serialized as JSON so that we have full access to the structural data.
    """
    # Convert AST to JSON string if it isn't already a string
    ast_json = ast if isinstance(ast, str) else json.dumps(ast)
    
    # Optionally compute the embedding using the JSON representation of AST.
    # (Our compute_embedding function expects a string input.)
    if embedding is None:
        embedding = compute_embedding(ast_json)
    
    query("""
        INSERT INTO code_snippets (repo_id, file_path, ast, embedding)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (repo_id, file_path) DO UPDATE 
        SET ast = EXCLUDED.ast, embedding = EXCLUDED.embedding;
    """, (repo_id, file_path, ast_json, embedding))
    log(f"Indexed code for repo_id {repo_id} at {file_path}")

def search_code(query_text: str, active_repo_id: int | None = None, limit: int = 5) -> list[dict]:
    """
    Searches for code snippets by computing the embedding of the query text,
    then comparing it with the stored embeddings.

    If active_repo_id is provided, filters results to include only those code snippets
    that are either part of the active project itself or belong to a reference repo linked
    to that active project.

    Args:
        query_text: The text query for code.
        active_repo_id: Optional active repository ID for filtering.
        limit: Maximum number of results.
        
    Returns:
        A list of code snippet records.
    """
    query_embedding = compute_embedding(query_text)
    vector_literal = to_pgvector_literal(query_embedding)
    
    base_sql = """
    SELECT cs.id, cs.repo_id, cs.file_path, cs.ast,
           cs.embedding <=> %s::vector AS similarity
    FROM code_snippets cs
    """
    params = [vector_literal]
    if active_repo_id is not None:
        base_sql += """
        JOIN repositories r ON cs.repo_id = r.id
        WHERE (r.id = %s OR r.active_repo_id = %s)
        """
        params.extend([active_repo_id, active_repo_id])
    else:
        base_sql += " WHERE 1=1 "
    base_sql += " ORDER BY similarity ASC LIMIT %s;"
    params.append(limit)
    
    return query(base_sql, tuple(params))

def search_docs(query_text: str, active_repo_id: int | None = None, limit: int = 5) -> list[dict]:
    """
    Searches for documentation snippets by matching the query text within the content.
    
    If active_repo_id is provided, filters documentation to include only those docs
    linked to the active project (either directly or via reference repos).
    
    Args:
        query_text: The text query for documentation.
        active_repo_id: Optional active repository ID to filter documentation.
        limit: Maximum number of results.
    
    Returns:
        A list of documentation records.
    """
    base_sql = """
    SELECT d.id, d.repo_id, d.file_path, d.content
    FROM repo_docs d
    """
    params = []
    if active_repo_id is not None:
        base_sql += """
        JOIN repositories r ON d.repo_id = r.id
        WHERE (r.id = %s OR r.active_repo_id = %s) AND d.content ILIKE %s
        """
        params.extend([active_repo_id, active_repo_id, f"%{query_text}%"])
    else:
        base_sql += " WHERE d.content ILIKE %s"
        params.append(f"%{query_text}%")
    base_sql += " LIMIT %s;"
    params.append(limit)
    
    return query(base_sql, tuple(params))

def compute_code_embedding(code_text: str):
    try:
        embedding = code_embedder.embed(code_text)
        return embedding
    except Exception as e:
        log(f"Error computing code embedding: {e}", level="error")
        return None