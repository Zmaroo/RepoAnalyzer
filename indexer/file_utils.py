"""File utility functions."""

import os
import fnmatch
from typing import List, Set, Optional
from utils.logger import log
from parsers.models import FileType, FileClassification, FileConfig

# Global config instance
file_config = FileConfig.create()

def should_ignore(path: str) -> bool:
    """Check if path should be ignored."""
    path_parts = os.path.normpath(path).split(os.sep)
    
    # Check directory ignores
    if any(part in file_config.ignored_dirs for part in path_parts):
        return True
        
    # Check file ignores
    filename = os.path.basename(path)
    if any(fnmatch.fnmatch(filename, pattern) for pattern in file_config.ignored_files):
        return True
        
    # Check patterns
    return any(fnmatch.fnmatch(path, pattern) for pattern in file_config.ignored_patterns)

def is_binary_file(file_path: str) -> bool:
    """Check if file is binary based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in file_config.binary_extensions

def get_file_classification(file_path: str) -> Optional[FileClassification]:
    """Get file classification."""
    try:
        if should_ignore(file_path):
            return None
            
        if is_binary_file(file_path):
            return FileClassification(FileType.BINARY)
            
        # Rest of classification logic...
        
    except Exception as e:
        log(f"Error classifying file {file_path}: {e}", level="error")
        return None

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