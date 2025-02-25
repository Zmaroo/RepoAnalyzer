"""File utility functions."""

import os
try:
    import magic
except AttributeError as e:
    raise ImportError(
        "Failed to load the 'magic' module because libmagic is missing or not linked correctly. "
        "Please install libmagic. On macOS, you can run: brew install libmagic"
    ) from e
from pathlib import Path
from typing import List, Set, Optional
from utils.logger import log
from parsers.models import FileType, FileClassification
from parsers.types import ParserType
from config import FileConfig

# Global config instance
file_config = FileConfig.create()

def should_ignore(file_path: str) -> bool:
    """Check if file should be ignored based on patterns."""
    ignore_patterns = {
        '.git',
        '__pycache__',
        'node_modules',
        'venv',
        '.env',
        '.idea',
        '.vscode'
    }
    
    path_parts = Path(file_path).parts
    return any(pattern in path_parts for pattern in ignore_patterns)

def is_binary_file(file_path: str) -> bool:
    """Check if file is binary using magic numbers."""
    try:
        mime = magic.from_file(file_path, mime=True)
        return not mime.startswith(('text/', 'application/json', 'application/xml'))
    except Exception as e:
        log(f"Error checking if file is binary {file_path}: {e}", level="error")
        return True

def get_file_classification(file_path: str) -> Optional[FileClassification]:
    """
    Get file classification based on extension and content.
    Returns FileClassification or None if file should be ignored.
    """
    try:
        if should_ignore(file_path):
            return None
            
        if is_binary_file(file_path):
            return FileClassification(
                file_type=FileType.BINARY,
                language_id="binary",
                parser_type=ParserType.CUSTOM
            )

        extension = Path(file_path).suffix.lower()
        
        # Code files
        if extension in {'.py', '.js', '.java', '.cpp', '.c', '.h', '.rs', '.go', '.rb', '.php'}:
            return FileClassification(
                file_type=FileType.CODE,
                language_id=extension[1:],  # Remove the dot
                parser_type=ParserType.TREE_SITTER
            )
            
        # Documentation files
        if extension in {'.md', '.rst', '.txt', '.adoc', '.asciidoc'}:
            doc_types = {
                '.md': 'markdown',
                '.rst': 'restructuredtext',
                '.txt': 'plaintext',
                '.adoc': 'asciidoc',
                '.asciidoc': 'asciidoc'
            }
            return FileClassification(
                file_type=FileType.DOC,
                language_id=doc_types[extension],
                parser_type=ParserType.CUSTOM
            )
            
        # Configuration files
        if extension in {'.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.env'}:
            config_types = {
                '.json': 'json',
                '.yaml': 'yaml',
                '.yml': 'yaml',
                '.toml': 'toml',
                '.ini': 'ini',
                '.conf': 'ini',
                '.env': 'env'
            }
            return FileClassification(
                file_type=FileType.CONFIG,
                language_id=config_types[extension],
                parser_type=ParserType.CUSTOM
            )

        # Default to unknown for unrecognized files
        return FileClassification(
            file_type=FileType.UNKNOWN,
            language_id="unknown",
            parser_type=ParserType.CUSTOM
        )
            
    except Exception as e:
        log(f"Error classifying file {file_path}: {e}", level="error")
        return None

def get_files(base_path: str, file_types: Set = None) -> List[str]:
    """Get all processable files in directory."""
    if file_types is None:
        file_types = {"CODE", "DOC"}  # Adjust according to your FileType definitions
        
    files = []
    try:
        for root, _, filenames in os.walk(base_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                
                # Skip ignored files
                if should_ignore(file_path):
                    continue
                    
                # Check file type
                classification = get_file_classification(file_path)
                if classification and classification.file_type in file_types:
                    files.append(file_path)
                    
        return files
    except Exception as e:
        log(f"Error getting files: {e}", level="error")
        return []

def get_relative_path(file_path: str, base_path: str) -> str:
    """Get relative path from base_path."""
    try:
        return os.path.relpath(file_path, base_path)
    except Exception as e:
        log(f"Error getting relative path: {e}", level="error")
        return file_path

def is_processable_file(file_path: str) -> bool:
    """Check if file can be processed."""
    try:
        classification = get_file_classification(file_path)
        return (classification is not None and 
                classification.file_type in {FileType.CODE, FileType.DOC})
    except Exception as e:
        log(f"Error checking file processability: {e}", level="error")
        return False