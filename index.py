import faulthandler
faulthandler.enable()

import os
import threading
from db.schema import create_all_tables
from semantic.semantic_search import search_code
from indexer.doc_index import search_docs
from watcher.file_watcher import start_file_watcher
from indexer.clone_and_index import get_or_create_repo, index_active_project
from utils.logger import log
import time
from ai_tools.ai_interface import AIAssistantInterface

def main():
    # Create tables if they do not exist
    create_all_tables()
    log("Database tables are set up.")

    # Index the active project files (initial indexing)
    index_active_project()
    log("Active project initial indexing started.")

    # Start the file watcher in a separate thread
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    log("File watcher started for active project.")

    # Allow some time for the initial indexing
    time.sleep(2)

    # Get or create the active repository
    active_repo_id = get_or_create_repo("active")

    # Initialize the unified AI assistant interface
    ai_assistant = AIAssistantInterface()
    log("AI assistant interface initialized.")

    try:
        # Analyze the repository using the unified AI interface
        analysis = ai_assistant.analyze_repository(active_repo_id)
        log(f"Repository analysis completed: {analysis}")

        # Example: Search for code snippets matching the query 'def'
        code_results = ai_assistant.search_code_snippets("def", repo_id=active_repo_id, limit=3)
        log(f"Code search results (active): {code_results}")

        # Additional usage examples:
        # similar_code = ai_assistant.find_similar_code("path/to/file.py", active_repo_id)
        # log(f"Similar code: {similar_code}")
        # flow = ai_assistant.trace_code_flow("path/to/entry_point.py", active_repo_id)
        # log(f"Code flow trace: {flow}")

        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Exiting.")
    finally:
        ai_assistant.close()

if __name__ == "__main__":
    main()