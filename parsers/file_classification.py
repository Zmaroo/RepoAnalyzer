"""File classification and type detection system."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Any
from enum import Enum
import os
import fnmatch
from utils.logger import log

class FileType(Enum):
    """File type categories."""
    CODE = "code"
    DOC = "doc"
    BINARY = "binary"
    CONFIG = "config"
    DATA = "data"
    UNKNOWN = "unknown"

@dataclass
class FileClassification:
    """File classification information."""
    file_type: FileType
    parser: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class FileClassifier:
    """Unified file classification system."""
    
    def __init__(self):
        self._classification_cache: Dict[str, FileClassification] = {}
        self._binary_extensions = {
            # Document formats
            '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
            # Images
            '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.webp',
            # Audio/Video
            '.mp3', '.mp4', '.wav', '.avi', '.mov',
            # Archives
            '.zip', '.tar', '.gz', '.rar', '.7z',
            # Compiled
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe'
        }
        self._ignored_dirs = {
            '.git', '.svn', 'node_modules', '__pycache__',
            'venv', '.env', '.venv', 'build', 'dist'
        }
        self._ignored_files = {
            '.DS_Store', 'Thumbs.db', '.gitignore'
        }
        self._ignored_patterns = {
            '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll',
            '*.exe', '*.obj', '*.o'
        }
    
    def should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_parts = os.path.normpath(path).split(os.sep)
        
        # Check directory ignores
        if any(part in self._ignored_dirs for part in path_parts):
            return True
            
        # Check file ignores
        filename = os.path.basename(path)
        if filename in self._ignored_files:
            return True
            
        # Check patterns
        return any(fnmatch.fnmatch(filename, pattern) 
                  for pattern in self._ignored_patterns)
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self._binary_extensions
    
    def get_classification(self, file_path: str) -> Optional[FileClassification]:
        """Get file classification with caching."""
        try:
            if file_path in self._classification_cache:
                return self._classification_cache[file_path]
                
            if self.should_ignore(file_path):
                return None
                
            if self.is_binary_file(file_path):
                classification = FileClassification(FileType.BINARY)
            else:
                # Determine file type and parser based on extension
                classification = self._classify_by_extension(file_path)
                
            self._classification_cache[file_path] = classification
            return classification
            
        except Exception as e:
            log(f"Error classifying file {file_path}: {e}", level="error")
            return None
    
    def _classify_by_extension(self, file_path: str) -> FileClassification:
        """Classify file based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        
        # Documentation files
        if ext in {'.md', '.rst', '.txt', '.docx', '.pdf'}:
            return FileClassification(FileType.DOC)
            
        # Configuration files
        if ext in {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'}:
            return FileClassification(FileType.CONFIG)
            
        # Data files
        if ext in {'.csv', '.xml', '.json', '.yaml', '.yml'}:
            return FileClassification(FileType.DATA)
            
        # Code files - parser will be determined by language registry
        if ext in {'.py', '.js', '.java', '.cpp', '.h', '.cs', '.go', '.rs'}:
            return FileClassification(FileType.CODE)
            
        return FileClassification(FileType.UNKNOWN)
    
    def clear_cache(self):
        """Clear classification cache."""
        self._classification_cache.clear()

# Global instance
file_classifier = FileClassifier()

# Convenience function
def get_file_classification(file_path: str) -> Optional[FileClassification]:
    """Get file classification for a path."""
    return file_classifier.get_classification(file_path)

def is_processable_file(file_path: str) -> bool:
    """Check if file can be processed."""
    try:
        classification = get_file_classification(file_path)
        return (classification is not None and 
                classification.file_type in {FileType.CODE, FileType.DOC})
    except Exception as e:
        log(f"Error checking file processability: {e}", level="error")
        return False 