import threading
from semantic.semantic_search import create_code_table, search_code
from docs.doc_index import create_docs_table, search_docs
from watcher.file_watcher import start_file_watcher
from indexer.clone_and_index import clone_and_index_repo
from utils.logger import log
import time

def main():
    # Create tables if they do not exist
    create_code_table()
    create_docs_table()
    log("Database tables are set up.")

    # Start file watcher in a separate thread for the active project
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    log("File watcher started for active project.")

    # Optionally, clone and index a reference repository (example: pydantic)
    clone_and_index_repo("https://github.com/samuelcolvin/pydantic.git", "pydantic")

    # Example queries:
    time.sleep(2)  # Wait a moment for indexing to finish
    code_results = search_code("def", repo_id="active", limit=3)
    log(f"Code search results (active): {code_results}")

    doc_results = search_docs("installation", repo_id="active", limit=3)
    log(f"Doc search results (active): {doc_results}")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Exiting.")

if __name__ == "__main__":
    main()