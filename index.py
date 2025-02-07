import faulthandler
faulthandler.enable()

import os
# Removed logging disablement so that logging is now enabled.
# os.environ["DISABLE_LOGGING"] = "True"  # This line has been removed

import threading
from db.schema import create_all_tables
from semantic.semantic_search import search_code
from indexer.doc_index import search_docs
from watcher.file_watcher import start_file_watcher
from indexer.clone_and_index import get_or_create_repo, index_active_project
# from indexer.clone_and_index import clone_and_index_repo  # Removed for active project indexing only
from utils.logger import log
import time

def main():
    # Create tables if they do not exist
    create_all_tables()
    log("Database tables are set up.")

    # Index the active project files (initial indexing)
    index_active_project()  # This function scans and indexes the current project directory
    log("Active project initial indexing started.")

    # Start the file watcher in a separate thread (this will pick up file changes)
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    log("File watcher started for active project.")

    # Allow some time for the initial indexing
    time.sleep(2)

    # Run example queries
    active_repo_id = get_or_create_repo("active")
    code_results = search_code("def", repo_id=active_repo_id, limit=3)
    log(f"Code search results (active): {code_results}")

    doc_results = search_docs("installation", repo_id=active_repo_id, limit=3)
    log(f"Doc search results (active): {doc_results}")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Exiting.")

if __name__ == "__main__":
    main()