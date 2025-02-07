import os
import asyncio
from indexer.file_config import CODE_EXTENSIONS, DOC_EXTENSIONS
from semantic.semantic_search import upsert_code
from indexer.doc_index import upsert_doc
from utils.logger import log
from parsers.file_parser import process_file
from indexer.async_utils import async_read_text_file
from indexer.common_indexer import async_index_files

async def async_index_repository(repo_path: str, repo_id: int) -> None:
    log(f"Indexing repository [{repo_id}] at: {repo_path}")
    # Asynchronously index code files—wrap the synchronous process_file with asyncio.to_thread
    await async_index_files(repo_path, repo_id, CODE_EXTENSIONS, process_file, upsert_code, "code", wrap_sync=True)
    # Asynchronously index documentation files (using an async file reader)
    await async_index_files(repo_path, repo_id, DOC_EXTENSIONS, async_read_text_file, upsert_doc, "doc") 