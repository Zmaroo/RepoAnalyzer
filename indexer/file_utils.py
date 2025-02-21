"""File utility functions."""

import os
from typing import List, Set
from utils.logger import log
from parsers.file_classification import (
    FileType, get_file_classification, 
    is_processable_file, file_classifier
)

def get_files(base_path: str, file_types: Set[FileType] = None) -> List[str]:
    """Get all processable files in directory."""
    if file_types is None:
        file_types = {FileType.CODE, FileType.DOC}
        
    files = []
    try:
        for root, _, filenames in os.walk(base_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                
                # Skip ignored files
                if file_classifier.should_ignore(file_path):
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