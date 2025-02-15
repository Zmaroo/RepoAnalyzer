import os
from typing import List, Set, Callable, Optional
from utils.logger import log
from parsers.language_mapping import get_language_for_extension

def get_files(dir_path: str, extensions: Set[str], ignore_dirs: Optional[Set[str]] = None) -> List[str]:
    """
    Recursively collects files from dir_path that have one of the specified extensions.
    Uses os.scandir for performance and optionally ignores directories in ignore_dirs.
    """
    if ignore_dirs is None:
        ignore_dirs = {'.git', '__pycache__'}
    files: List[str] = []

    def _recurse(path: str) -> None:
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in ignore_dirs:
                            continue
                        _recurse(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1]
                        if ext.lower() in extensions:
                            files.append(entry.path)
        except Exception as e:
            log(f"Error scanning directory {path}: {e}", level="error")

    _recurse(dir_path)
    return files

def is_binary_file(file_path: str, blocksize: int = 1024) -> bool:
    """
    Checks if the file is binary by reading up to blocksize bytes.
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(blocksize)
            if b'\0' in chunk:
                return True
    except Exception as e:
        log(f"Error reading file {file_path} for binary check: {e}", level="error")
    return False

def read_text_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    Reads and returns the content of a text file using the specified encoding.
    Returns an empty string (and logs the error) if any error is encountered.
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception as e:
        log(f"Error reading text file {file_path}: {e}", level="error")
    return ""

def process_index_file(
    file_path: str,
    base_path: str,
    repo_id: int,
    file_processor: Callable[[str], Optional[str]],
    index_function: Callable[[int, str, str], None],
    file_type: str
) -> None:
    """
    [Deprecated]
    
    Processes a file for indexing in a standardized way.
    Prefer using the asynchronous index_file_async() from indexer/common_indexer.
    """
    try:
        if is_binary_file(file_path):
            log(f"Skipping binary file: {file_path}", level="warning")
            return
        result = file_processor(file_path)
        if not result:
            log(f"No result from processing {file_path}", level="debug")
            return
        rel_path = os.path.relpath(file_path, base_path)
        index_function(repo_id, rel_path, result)
        log(f"Indexed {file_type} file: {rel_path}", level="info")
    except Exception as e:
        log(f"Error processing {file_type} file {file_path}: {e}", level="error")