from db.psql import query
from transformers import AutoTokenizer, AutoModel
import torch

# Load GraphCodeBERT model and tokenizer (lazy initialization)
_model = None
_tokenizer = None

def init_model():
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
        _model = AutoModel.from_pretrained("microsoft/graphcodebert-base")

def compute_embedding(text: str) -> list[float]:
    """
    Compute a high-quality embedding for the given code using GraphCodeBERT.
    Returns a list of floats (the embedding vector).
    """
    init_model()
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = _model(**inputs)
    # Use the embedding of the [CLS] token
    cls_embedding = outputs.last_hidden_state[:, 0, :]
    embedding = cls_embedding.squeeze().tolist()  # typically a vector of dimension 768
    return embedding

def create_code_table():
    sql = """
    CREATE TABLE IF NOT EXISTS code_snippets (
      id SERIAL PRIMARY KEY,
      repo_id TEXT NOT NULL,
      file_path TEXT NOT NULL,
      ast TEXT,
      embedding vector(768),
      UNIQUE(repo_id, file_path)
    );
    """
    query(sql)

def upsert_code(repo_id: str, file_path: str, ast: str):
    embedding = compute_embedding(ast)  # Here, we embed the AST representation.
    # Check if record exists
    find_sql = "SELECT id FROM code_snippets WHERE repo_id = %s AND file_path = %s;"
    result = query(find_sql, (repo_id, file_path))
    if result:
        update_sql = "UPDATE code_snippets SET ast = %s, embedding = %s WHERE repo_id = %s AND file_path = %s;"
        query(update_sql, (ast, str(embedding), repo_id, file_path))
        print(f"Updated code snippet for [{repo_id}] {file_path}")
    else:
        insert_sql = """
        INSERT INTO code_snippets (repo_id, file_path, ast, embedding)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
        """
        result = query(insert_sql, (repo_id, file_path, ast, str(embedding)))
        print(f"Inserted code snippet with id {result[0]['id']} for [{repo_id}] {file_path}")

def search_code(query_text: str, repo_id: str | None = None, limit: int = 5) -> list[dict]:
    # A simple text-based search on the AST column; replace with vector similarity search if needed.
    sql = """
    SELECT id, repo_id, file_path, ast
    FROM code_snippets
    WHERE ast ILIKE %s
    """
    params: tuple = (f"%{query_text}%",)
    if repo_id:
        sql += " AND repo_id = %s"
        params += (repo_id,)
    sql += " LIMIT %s;"
    params += (limit,)
    return query(sql, params)