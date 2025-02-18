import os
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from semantic.semantic_search import upsert_code
from indexer.doc_index import upsert_doc
from utils.logger import log
from parsers.file_parser import process_file
from indexer.file_utils import read_text_file
from indexer.common_indexer import index_files
from parsers.language_mapping import FileType, get_file_classification
from parsers.file_parser import FileProcessor

def index_repository(repo_path: str, repo_id: int) -> None:
    """Index a reference repository (e.g., dependency project)"""
    log(f"Indexing reference repository [{repo_id}] at: {repo_path}")
    
    # Get files by FileType instead of extensions
    processor = FileProcessor()
    
    # Index code files
    index_files(
        repo_path=repo_path,
        repo_id=repo_id,
        file_types={FileType.CODE},
        file_processor=processor.process_file,
        index_function=upsert_code,
        file_type="reference_code"
    )
    
    # Index documentation files
    index_files(
        repo_path=repo_path,
        repo_id=repo_id,
        file_types={FileType.DOC},
        file_processor=read_text_file,
        index_function=upsert_doc,
        file_type="reference_doc"
    )