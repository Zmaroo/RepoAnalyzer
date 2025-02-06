from db.psql import query

def create_docs_table():
    sql = """
    CREATE TABLE IF NOT EXISTS repo_docs (
      id SERIAL PRIMARY KEY,
      repo_id TEXT NOT NULL,
      file_path TEXT NOT NULL,
      content TEXT NOT NULL,
      UNIQUE(repo_id, file_path)
    );
    """
    query(sql)

def upsert_doc(repo_id: str, file_path: str, content: str):
    find_sql = "SELECT id FROM repo_docs WHERE repo_id = %s AND file_path = %s;"
    result = query(find_sql, (repo_id, file_path))
    if result:
        update_sql = "UPDATE repo_docs SET content = %s WHERE repo_id = %s AND file_path = %s;"
        query(update_sql, (content, repo_id, file_path))
        print(f"Updated doc for [{repo_id}] {file_path}")
    else:
        insert_sql = """
        INSERT INTO repo_docs (repo_id, file_path, content)
        VALUES (%s, %s, %s)
        RETURNING id;
        """
        result = query(insert_sql, (repo_id, file_path, content))
        print(f"Inserted doc with id {result[0]['id']} for [{repo_id}] {file_path}")

def search_docs(query_text: str, repo_id: str | None = None, limit: int = 5) -> list[dict]:
    sql = """
    SELECT id, repo_id, file_path, content
    FROM repo_docs
    WHERE content ILIKE %s
    """
    params: tuple = (f"%{query_text}%",)
    if repo_id:
        sql += " AND repo_id = %s"
        params += (repo_id,)
    sql += " LIMIT %s;"
    params += (limit,)
    return query(sql, params)