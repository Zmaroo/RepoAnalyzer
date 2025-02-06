import os
from parsers.file_parser import process_file
from semantic.semantic_search import upsert_code
from docs.doc_index import upsert_doc
from utils.logger import log

CODE_EXTENSIONS = {'.py', '.java', '.js', '.ts', '.c', '.cpp', '.rs', '.go', '.rb'}
DOC_EXTENSIONS = {'.md', '.txt', '.rst'}

def get_files(dir_path: str, extensions: set[str]) -> list[str]:
    files = []
    for root, _, filenames in os.walk(dir_path):
        for filename in filenames:
            if os.path.splitext(filename)[1] in extensions:
                files.append(os.path.join(root, filename))
    return files

def index_repository(repo_path: str, repo_id: str):
    log(f"Indexing repository [{repo_id}] at: {repo_path}")
    code_files = get_files(repo_path, CODE_EXTENSIONS)
    log(f"Found {len(code_files)} code files in [{repo_id}].")
    for file_path in code_files:
        try:
            ast = process_file(file_path)
            if ast:
                rel_path = os.path.relpath(file_path, repo_path)
                upsert_code(repo_id, rel_path, ast)
                log(f"Indexed code: {rel_path}")
        except Exception as e:
            log(f"Error indexing code file {file_path}: {e}")

    doc_files = get_files(repo_path, DOC_EXTENSIONS)
    log(f"Found {len(doc_files)} doc files in [{repo_id}].")
    for file_path in doc_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            rel_path = os.path.relpath(file_path, repo_path)
            upsert_doc(repo_id, rel_path, content)
            log(f"Indexed doc: {rel_path}")
        except Exception as e:
            log(f"Error indexing doc file {file_path}: {e}")