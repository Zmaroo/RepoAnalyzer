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
from db.schema import create_all_tables
from watcher.file_watcher import start_file_watcher
from indexer.clone_and_index import get_or_create_repo, index_active_project
from utils.logger import log
import time
from ai_tools.ai_interface import AIAssistantInterface
import asyncio
from indexer.async_indexer import async_index_code, async_index_docs

def main():
    # Create tables if they do not exist.
    create_all_tables()
    log("Database tables are set up.")

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
    # Example usage for development
    repository_id = 1
    base_path = "./path/to/repo"
    index_repository(repository_id, base_path)