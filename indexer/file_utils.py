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
from parsers.types import FileType
from parsers.models import FileClassification
from parsers.types import ParserType
from parsers.language_mapping import is_binary_extension, BINARY_EXTENSIONS
from config import FileConfig
# Import the file classification module
from parsers.file_classification import classify_file as parsers_classify_file
from utils.error_handling import handle_errors, ErrorBoundary

# Global config instance
file_config = FileConfig.create()

def should_ignore(file_path: str) -> bool:
    """
    Check if file should be ignored based on patterns.
    
    Args:
        file_path: The path to check
        
    Returns:
        True if the file should be ignored, False otherwise
    """
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

@handle_errors(error_types=(Exception,))
def is_binary_file(file_path: str) -> bool:
    """
    Check if file is binary using magic numbers.
    
    Args:
        file_path: The path to check
        
    Returns:
        True if the file is binary, False otherwise
    """
    try:
        # Check extension first for efficiency
        _, ext = os.path.splitext(file_path)
        if is_binary_extension(ext):
            return True
        
        # Use libmagic for more accurate detection
        mime = magic.from_file(file_path, mime=True)
        return not mime.startswith(('text/', 'application/json', 'application/xml'))
    except Exception as e:
        log(f"Error checking if file is binary {file_path}: {e}", level="error")
        return True

@handle_errors(error_types=(Exception,))
def get_file_classification(file_path: str) -> Optional[FileClassification]:
    """
    Get file classification based on extension and content.
    Returns FileClassification or None if file should be ignored.
    
    This function delegates to the centralized file classification system
    in parsers.file_classification.
    
    Args:
        file_path: The path to classify
        
    Returns:
        FileClassification object or None if file should be ignored
    """
    try:
        if should_ignore(file_path):
            return None
            
        # Use the parsers' classify_file function but handle binary detection here
        # since we have magic library available for more accurate detection
        is_binary = is_binary_file(file_path)
        if is_binary:
            return FileClassification(
                file_path=file_path,
                language_id="binary",
                parser_type=ParserType.CUSTOM,
                file_type=FileType.DATA,
                is_binary=True
            )
            
        # For text files, use the comprehensive classifier
        return parsers_classify_file(file_path)
            
    except Exception as e:
        log(f"Error classifying file {file_path}: {e}", level="error")
        return None

def get_files(base_path: str, file_types: Set = None) -> List[str]:
    """
    Get all processable files in directory.
    
    Args:
        base_path: The root directory to search
        file_types: Optional set of FileType values to include
        
    Returns:
        List of file paths
    """
    if file_types is None:
        file_types = {FileType.CODE, FileType.DOC}  # Use enum values
        
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
    """
    Get relative path from base_path.
    
    Args:
        file_path: The absolute file path
        base_path: The base directory path
        
    Returns:
        Relative path string
    """
    try:
        return os.path.relpath(file_path, base_path)
    except Exception as e:
        log(f"Error getting relative path: {e}", level="error")
        return file_path

def is_processable_file(file_path: str) -> bool:
    """
    Check if file can be processed.
    
    Args:
        file_path: The file path to check
        
    Returns:
        True if file can be processed, False otherwise
    """
    try:
        classification = get_file_classification(file_path)
        return (classification is not None and 
                classification.file_type in {FileType.CODE, FileType.DOC})
    except Exception as e:
        log(f"Error checking file processability: {e}", level="error")
        return False