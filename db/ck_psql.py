from db.psql import query, close_db_pool
import asyncio
from pprint import pprint

async def check_all_postgres_tables():
    print("\n==========================================")
    print("     PostgreSQL Database Check")
    print("==========================================\n")
    
    # Dictionary defining table names and their corresponding queries.
    tables = {
        "Repositories": "SELECT * FROM repositories ORDER BY id;",
        "Code Snippets": "SELECT * FROM code_snippets ORDER BY id;",
        "Repository Documents": "SELECT * FROM repo_docs ORDER BY id;",
        "Repo Doc Relations": "SELECT * FROM repo_doc_relations ORDER BY repo_id, doc_id;",
        "Document Versions": "SELECT * FROM doc_versions ORDER BY id;",
        "Document Clusters": "SELECT * FROM doc_clusters ORDER BY id;"
    }
    
    for table_name, sql in tables.items():
        try:
            records = await query(sql)
            print(f"{table_name}:")
            print("-" * len(table_name))
            print(f"Total entries: {len(records)}")
            for record in records:
                pprint(dict(record))
            print("\n")
        except Exception as e:
            print(f"Error querying {table_name}: {e}")
    
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(check_all_postgres_tables())