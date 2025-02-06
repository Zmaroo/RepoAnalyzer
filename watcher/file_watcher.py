import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
from parsers.file_parser import process_file
from semantic.semantic_search import upsert_code
from docs.doc_index import upsert_doc
from utils.logger import log

# Define file extensions
CODE_EXTENSIONS = {'.py', '.java', '.js', '.ts', '.c', '.cpp', '.rs', '.go', '.rb'}
DOC_EXTENSIONS = {'.md', '.txt', '.rst'}

ACTIVE_REPO_ID = "active"

class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        ext = os.path.splitext(file_path)[1]
        # Use structural pattern matching
        match ext:
            case _ if ext in CODE_EXTENSIONS:
                ast = process_file(file_path)
                if ast:
                    upsert_code(ACTIVE_REPO_ID, file_path, ast)
                    log(f"Indexed code file: {file_path}")
            case _ if ext in DOC_EXTENSIONS:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    upsert_doc(ACTIVE_REPO_ID, file_path, content)
                    log(f"Indexed doc file: {file_path}")
                except Exception as e:
                    log(f"Error processing doc file {file_path}: {e}")
            case _:
                log(f"Ignored file: {file_path}")

def start_file_watcher():
    path_to_watch = os.getcwd()
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path_to_watch, recursive=True)
    observer.start()
    log(f"Watching directory: {path_to_watch}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_file_watcher()