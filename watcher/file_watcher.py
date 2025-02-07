import time
import os
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from parsers.file_parser import process_file as sync_process_file
from semantic.semantic_search import upsert_code
from indexer.doc_index import upsert_doc
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from utils.logger import log
from indexer.clone_and_index import get_or_create_repo
from indexer.async_utils import async_process_index_file, async_read_text_file
from utils.async_runner import submit_async_task

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, active_repo_id: int, active_project_root: str):
        self.active_repo_id = active_repo_id
        self.active_project_root = active_project_root
        super().__init__()

    def on_modified(self, event) -> None:
        if event.is_directory:
            return

        abs_file_path = event.src_path
        rel_file_path = os.path.relpath(abs_file_path, self.active_project_root)
        log(f"Detected change in file (abs: {abs_file_path}, rel: {rel_file_path})", level="debug")
        ext = os.path.splitext(abs_file_path)[1].lower()

        # Mapping file type settings to processor and index function
        file_type_configs = [
            (CODE_EXTENSIONS, lambda fp: asyncio.to_thread(sync_process_file, fp), upsert_code, "code"),
            (DOC_EXTENSIONS, async_read_text_file, upsert_doc, "doc")
        ]
        
        for ext_set, processor, index_func, file_type in file_type_configs:
            if ext in ext_set:
                submit_async_task(
                    async_process_index_file(
                        file_path=abs_file_path,
                        base_path=self.active_project_root,
                        repo_id=self.active_repo_id,
                        file_processor=processor,
                        index_function=index_func,
                        file_type=file_type
                    )
                )
                return

        log(f"Ignored file {abs_file_path} (relative: {rel_file_path})", level="debug")

def start_file_watcher(path: str = ".") -> None:
    # Delay active repo initialization until this function is called (after tables are created)
    active_repo_id = get_or_create_repo("active")
    active_project_root = os.getcwd()
    event_handler = ChangeHandler(active_repo_id, active_project_root)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_file_watcher()