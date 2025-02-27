from .clone_and_index import clone_and_index_repo, get_or_create_repo
from .file_processor import FileProcessor
from .file_utils import get_file_classification, get_files, get_relative_path, is_processable_file
from .unified_indexer import (
    index_active_project,
    index_active_project_sync,
    process_repository_indexing
)
from .async_utils import async_read_file, async_handle_errors, batch_process_files

# Initialize pattern system when indexer is imported
from parsers.query_patterns import initialize_pattern_system
initialize_pattern_system()

__all__ = [
    "clone_and_index_repo",
    "get_or_create_repo",
    "FileProcessor",
    "get_file_classification",
    "get_files",
    "get_relative_path",
    "is_processable_file",
    "index_active_project",
    "index_active_project_sync",
    "process_repository_indexing",
    "async_read_file",
    "async_handle_errors",
    "batch_process_files"
] 