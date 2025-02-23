from db.psql import query
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    DatabaseError,
    PostgresError
)
from parsers.models import (  # Add imports
    FileType,
    FileClassification,
    ParserResult,
    ExtractedFeatures
)
import asyncio
from db.transaction import transaction_scope
from indexer.async_utils import handle_async_errors, AsyncErrorBoundary

"""[6.6] Database schema management.

Flow:
1. Schema Operations:
   - Table creation/deletion
   - Index management
   - Vector storage setup

2. Integration Points:
   - FileProcessor [2.0]: Code and doc storage schema
   - SearchEngine [5.0]: Vector similarity indexes
   - UpsertOps [6.5]: Storage operations

3. Tables:
   - repositories: Project metadata
   - code_snippets: Code with embeddings
   - repo_docs: Documentation with embeddings
   - doc_versions: Version tracking
   - doc_clusters: Documentation grouping
"""

# Global schema lock
_schema_lock = asyncio.Lock()

class SchemaError(DatabaseError):
    """Schema management specific errors."""
    pass

async def drop_all_tables():
    """[6.6.4] Clean database state."""
    # Drop in correct order for foreign key constraints
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
    """[6.6.1] Create code storage with vector similarity support."""
    sql = """
    CREATE TABLE IF NOT EXISTS code_snippets (
        id SERIAL PRIMARY KEY,
        repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        ast TEXT,
        embedding VECTOR(768),  # GraphCodeBERT dimension
        enriched_features JSONB,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(repo_id, file_path)
    );
    CREATE INDEX IF NOT EXISTS idx_code_snippets_embedding 
    ON code_snippets USING ivfflat (embedding vector_cosine_ops);
    """
    await query(sql)

async def create_repo_docs_table():
    """[6.6.2] Create documentation storage with versioning."""
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
        metadata JSONB,
        quality_metrics JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    await query(sql_table)

    # Vector similarity index
    sql_index = """
    CREATE INDEX IF NOT EXISTS idx_repo_docs_embedding 
    ON repo_docs USING ivfflat (embedding vector_cosine_ops);
    """
    await query(sql_index)

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

@handle_async_errors(error_types=(SchemaError, PostgresError))
async def create_all_tables():
    """[6.6.3] Initialize complete database schema."""
    async with _schema_lock:
        try:
            async with transaction_scope() as txn:
                async with AsyncErrorBoundary("schema creation", error_types=(SchemaError, PostgresError)):
                    # Vector extension
                    await query("CREATE EXTENSION IF NOT EXISTS vector;")
                    
                    # Core tables in dependency order
                    tables = [
                        create_repositories_table,
                        create_code_snippets_table,
                        create_repo_docs_table,
                        create_repo_doc_relations_table,
                        create_doc_versions_table,
                        create_doc_clusters_table
                    ]
                    
                    for create_table in tables:
                        try:
                            await create_table()
                            log(f"Created table via {create_table.__name__}", level="debug")
                        except Exception as e:
                            raise SchemaError(f"Failed to create table {create_table.__name__}: {str(e)}")
                    
                    log("✅ Database tables are set up!", context={"tables": len(tables)})
                    
        except Exception as e:
            log("Schema creation failed", level="error", context={"error": str(e)})
            raise SchemaError(f"Complete schema creation failed: {str(e)}")