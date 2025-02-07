from db.psql import query
from utils.logger import log

def create_repositories_table():
    sql = """
    CREATE TABLE IF NOT EXISTS repositories (
        id SERIAL PRIMARY KEY,
        repo_name TEXT UNIQUE NOT NULL,
        source_url TEXT,
        repo_type TEXT DEFAULT 'active',  -- 'active' or 'reference'
        active_repo_id INTEGER,           -- If this is a reference repo, stores the ID of the active repo it is associated with.
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_active_repo
            FOREIGN KEY(active_repo_id)
                REFERENCES repositories(id)
                ON DELETE SET NULL
    );
    """
    query(sql)

def create_code_snippets_table():
    sql = """
    CREATE TABLE IF NOT EXISTS code_snippets (
        id SERIAL PRIMARY KEY,
        repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        ast TEXT,
        embedding VECTOR(768) NULL,
        UNIQUE(repo_id, file_path)
    );
    """
    query(sql)

def create_repo_docs_table():
    sql = """
    CREATE TABLE IF NOT EXISTS repo_docs (
        id SERIAL PRIMARY KEY,
        repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        content TEXT NOT NULL,
        embedding VECTOR(768) NULL,
        UNIQUE(repo_id, file_path)
    );
    """
    query(sql)

def create_all_tables():
    # Optional: Ensure necessary extensions exist.
    query("CREATE EXTENSION IF NOT EXISTS vector;")
    create_repositories_table()
    create_code_snippets_table()
    create_repo_docs_table()
    log("✅ Database tables are set up!")