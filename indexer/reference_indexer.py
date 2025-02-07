import os
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from semantic.semantic_search import upsert_code
from indexer.doc_index import upsert_doc
from utils.logger import log
from parsers.file_parser import process_file
from indexer.file_utils import read_text_file
from indexer.common_indexer import index_files

def index_repository(repo_path: str, repo_id: int) -> None:
    log(f"Indexing repository [{repo_id}] at: {repo_path}")
    # Synchronously index code files
    index_files(repo_path, repo_id, CODE_EXTENSIONS, process_file, upsert_code, "code")
    # Synchronously index documentation files
    index_files(repo_path, repo_id, DOC_EXTENSIONS, read_text_file, upsert_doc, "doc")