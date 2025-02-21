from db.psql import query
from utils.logger import log

async def drop_all_tables():
    # Drop dependent tables before primary ones.
    await query("DROP TABLE IF EXISTS repo_doc_relations CASCADE;")
    await query("DROP TABLE IF EXISTS doc_versions CASCADE;")
    await query("DROP TABLE IF EXISTS doc_clusters CASCADE;")
    await query("DROP TABLE IF EXISTS repo_docs CASCADE;")
    await query("DROP TABLE IF EXISTS code_snippets CASCADE;")
    await query("DROP TABLE IF EXISTS repositories CASCADE;")
    log("✅ All existing database tables dropped!")

async def create_repositories_table():
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
    await query(sql)

async def create_code_snippets_table():
    sql = """
    CREATE TABLE IF NOT EXISTS code_snippets (
        id SERIAL PRIMARY KEY,
        repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        ast TEXT,
        embedding VECTOR(768),  # GraphCodeBERT dimension
        enriched_features JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # Add timestamp
        UNIQUE(repo_id, file_path)
    );
    CREATE INDEX IF NOT EXISTS idx_code_snippets_embedding ON code_snippets USING ivfflat (embedding vector_cosine_ops);
    """
    await query(sql)

async def create_repo_docs_table():
    """Create the main documentation table along with its indexes."""
    # Create the table first.
    sql_table = """
    CREATE TABLE IF NOT EXISTS repo_docs (
        id SERIAL PRIMARY KEY,
        file_path TEXT NOT NULL,
        content TEXT NOT NULL,
        doc_type TEXT NOT NULL,  -- 'markdown', 'inline', 'docstring'
        version INTEGER DEFAULT 1,
        cluster_id INTEGER,
        related_code_path TEXT,  -- For linking to specific code files
        embedding VECTOR(768) NULL,
        metadata JSONB,          -- For additional metadata
        quality_metrics JSONB,   -- Store quality analysis
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    await query(sql_table)

    # Create indexes separately.
    sql_index1 = "CREATE INDEX IF NOT EXISTS idx_repo_docs_cluster ON repo_docs(cluster_id);"
    await query(sql_index1)

    sql_index2 = "CREATE INDEX IF NOT EXISTS idx_repo_docs_embedding ON repo_docs USING ivfflat (embedding vector_cosine_ops);"
    await query(sql_index2)

async def create_repo_doc_relations_table():
    """Create junction table for repo-doc relationships"""
    sql = """
    CREATE TABLE IF NOT EXISTS repo_doc_relations (
        repo_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
        doc_id INTEGER REFERENCES repo_docs(id) ON DELETE CASCADE,
        is_primary BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (repo_id, doc_id)
    );
    """
    await query(sql)

async def create_doc_versions_table():
    """Track document versions"""
    sql = """
    CREATE TABLE IF NOT EXISTS doc_versions (
        id SERIAL PRIMARY KEY,
        doc_id INTEGER REFERENCES repo_docs(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        version INTEGER NOT NULL,
        changes_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(doc_id, version)
    );
    """
    await query(sql)

async def create_doc_clusters_table():
    """Group related documentation"""
    sql = """
    CREATE TABLE IF NOT EXISTS doc_clusters (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        metadata JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    await query(sql)

async def create_all_tables():
    # Ensure necessary extensions exist.
    await query("CREATE EXTENSION IF NOT EXISTS vector;")
    await create_repositories_table()
    await create_code_snippets_table()
    await create_repo_docs_table()
    await create_repo_doc_relations_table()
    await create_doc_versions_table()
    await create_doc_clusters_table()
    log("✅ Database tables are set up!")