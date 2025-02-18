"""
Repository Indexing Entry Point

This module coordinates repository indexing. It makes use of the new
async_indexer functions to run asynchronous indexing tasks for both code
and documentation files.

Note:
  - Use this as the development/CLI entry point.
  - AI functionalities are independent and are handled in ai_tools/ai_interface.py.
"""

import faulthandler
faulthandler.enable()

import threading
import argparse
from db.schema import create_all_tables
from db.neo4j_schema import initialize_neo4j_schema  # Add Neo4j schema initialization
from watcher.file_watcher import start_file_watcher
from indexer.clone_and_index import get_or_create_repo, index_active_project
from utils.logger import log
import time
from ai_tools.ai_interface import AIAssistantInterface
import asyncio
from indexer.async_indexer import async_index_code, async_index_docs
from utils.db_utils import clean_postgresql, clean_neo4j  # Import cleaning utilities

def initialize_databases(clean: bool = False):
    """
    Initialize both PostgreSQL and Neo4j databases.
    Optionally clean them first if specified.
    """
    if clean:
        log("Cleaning databases before initialization...")
        if not clean_postgresql():
            log("Failed to clean PostgreSQL database.", level="error")
            return False
        if not clean_neo4j():
            log("Failed to clean Neo4j database.", level="error")
            return False
        log("Databases cleaned successfully.")

    # Initialize PostgreSQL schema
    create_all_tables()
    log("PostgreSQL tables are set up.")

    # Initialize Neo4j schema
    initialize_neo4j_schema()
    log("Neo4j schema initialized.")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Repository indexing and analysis tool.")
    parser.add_argument("--clean", action="store_true", 
                       help="Clean and reinitialize databases before starting")
    parser.add_argument("--search-docs", type=str,
                       help="Search for documentation by term")
    parser.add_argument("--share-docs", type=str,
                       help="Share docs (format: 'doc_id1,doc_id2:target_repo_id')")
    parser.add_argument("--analyze-docs", type=int,
                       help="Analyze documentation for repository ID")
    parser.add_argument("--suggest-docs", type=int,
                       help="Suggest relevant documentation for repository ID")
    parser.add_argument("--doc-quality", type=str,
                       help="Check documentation quality (format: 'repo_id:doc_id')")
    parser.add_argument("--cluster-docs", type=int,
                       help="Cluster documentation for repository ID")
    parser.add_argument("--suggest-improvements", type=int,
                       help="Get documentation improvement suggestions")
    parser.add_argument("--version-history", type=str,
                       help="Show version history (format: 'repo_id:doc_id')")
    args = parser.parse_args()

    # Initialize databases (optionally cleaning first)
    if not initialize_databases(clean=args.clean):
        log("Database initialization failed. Exiting.", level="error")
        return

    # Index the active project files (initial indexing).
    index_active_project()
    log("Active project initial indexing started.")

    # Start the file watcher in a separate thread.
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    log("File watcher started for active project.")

    # Allow some time for the initial indexing.
    time.sleep(2)

    # Get or create the active repository.
    active_repo_id = get_or_create_repo("active")

    # Initialize the unified AI assistant interface.
    ai_assistant = AIAssistantInterface()
    log("AI assistant interface initialized.")

    # Handle documentation commands
    if args.search_docs:
        docs = ai_assistant.search_documentation(args.search_docs)
        print("\nAvailable Documentation:")
        for doc in docs:
            print(f"ID: {doc['id']}")
            print(f"Path: {doc['file_path']}")
            print(f"Type: {doc['doc_type']}")
            print("---")
        return

    if args.share_docs:
        try:
            doc_ids_str, target_repo = args.share_docs.split(":")
            doc_ids = [int(id) for id in doc_ids_str.split(",")]
            result = ai_assistant.share_documentation(doc_ids, int(target_repo))
            print(f"\nSharing result: {result}")
        except ValueError:
            print("Invalid format. Use: --share-docs='doc_id1,doc_id2:target_repo_id'")
        return

    if args.analyze_docs:
        analysis = ai_assistant.analyze_documentation(args.analyze_docs)
        print("\nDocumentation Analysis:")
        print(f"Total Documents: {analysis['total_docs']}")
        print("\nDocument Types:")
        for doc_type, count in analysis['doc_types'].items():
            print(f"  {doc_type}: {count}")
        print("\nShared Documents:")
        for doc in analysis['shared_docs']:
            print(f"  {doc['path']} (shared with repos: {doc['shared_with']})")
        return

    if args.suggest_docs:
        suggestions = ai_assistant.suggest_documentation_links(args.suggest_docs)
        print("\nSuggested Documentation:")
        for suggestion in suggestions:
            print(f"ID: {suggestion['doc_id']}")
            print(f"Path: {suggestion['file_path']}")
            print(f"Relevance: {suggestion['relevance']:.2f}")
            print(f"Reason: {suggestion['reason']}")
            print("---")
        return

    if args.cluster_docs:
        clusters = ai_assistant.analyze_documentation(args.cluster_docs)['clusters']
        print("\nDocumentation Clusters:")
        for cluster_id, docs in clusters.items():
            print(f"\nCluster {cluster_id}:")
            for doc in docs:
                print(f"  {doc['path']} (similarity: {doc['similarity_score']:.2f})")
        return

    if args.suggest_improvements:
        suggestions = ai_assistant.suggest_documentation_improvements(args.suggest_improvements)
        print("\nSuggested Improvements:")
        for suggestion in suggestions:
            print(f"\nDocument ID: {suggestion['doc_id']}")
            print(f"Type: {suggestion['type']}")
            print(f"Suggestion: {suggestion['suggestion']}")
        return

    if args.version_history:
        try:
            repo_id, doc_id = map(int, args.version_history.split(":"))
            history = ai_assistant.analyze_documentation(repo_id)['version_history'].get(doc_id, {})
            print(f"\nVersion History for Document {doc_id}:")
            print(f"Total Versions: {history.get('version_count', 0)}")
            print(f"Last Updated: {history.get('last_updated', 'N/A')}")
            print("\nChanges Summary:")
            print(history.get('change_summary', 'No changes recorded'))
        except ValueError:
            print("Invalid format. Use: --version-history='repo_id:doc_id'")
        return

    try:
        # Analyze the repository using the unified AI interface.
        analysis = ai_assistant.analyze_repository(active_repo_id)
        log(f"Repository analysis completed: {analysis}")

        # Example: Search for code snippets matching the query 'def'.
        code_results = ai_assistant.search_code_snippets("def", repo_id=active_repo_id, limit=3)
        log(f"Code search results (active): {code_results}")

        # Keep the main thread alive.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Exiting.")
    finally:
        ai_assistant.close()

def index_repository(repo_id: int, base_path: str):
    """
    Initiates asynchronous indexing routines for both code and docs.
    """
    loop = asyncio.get_event_loop()
    tasks = [
        async_index_code(repo_id, base_path),
        async_index_docs(repo_id, base_path)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))

if __name__ == "__main__":
    main()