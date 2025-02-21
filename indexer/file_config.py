"""File configuration and binary detection."""

from dataclasses import dataclass, field
from typing import Set, Optional
from parsers.file_classification import FileType, get_file_classification
from parsers.language_support import language_registry
from utils.logger import log
from indexer.file_utils import is_processable_file, get_files

@dataclass(frozen=True)
class FileConfig:
    """Central configuration for file handling."""
    binary_extensions: Set[str] = field(default_factory=lambda: {
        # Document formats
        '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
        
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.webp',
        
        # Archives
        '.zip', '.tar', '.gz', '.rar', '.7z',
        
        # Binaries
        '.exe', '.dll', '.so', '.dylib',
        '.pyc', '.pyo', '.pyd',
        
        # Media
        '.mp3', '.mp4', '.wav', '.avi', '.mov',
        
        # Database
        '.db', '.sqlite', '.sqlite3'
    })
    
    @classmethod
    def create(cls) -> 'FileConfig':
        """Create a new FileConfig instance."""
        return cls()
    
    def is_binary_extension(self, file_path: str) -> bool:
        """Check if file has a binary extension."""
        return any(file_path.endswith(ext) for ext in self.binary_extensions)
    
    def is_processable(self, file_path: str) -> bool:
        """Check if a file should be processed."""
        return is_processable_file(file_path)
    
    def get_files_by_type(self, dir_path: str, file_types: Optional[Set[FileType]] = None) -> list[str]:
        """Get all processable files of specified types from directory."""
        return get_files(dir_path, file_types)
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get comprehensive file information."""
        try:
            classification = get_file_classification(file_path)
            if not classification:
                return None
                
            return {
                'file_path': file_path,
                'classification': classification,
                'file_type': classification.file_type.value,
                'is_processable': self.is_processable(file_path),
                'language': classification.parser,
                'has_parser': language_registry.is_language_supported(classification.parser) if classification.parser else False
            }
        except Exception as e:
            log(f"Error getting file info for {file_path}: {e}", level="error")
            return None

# Global instance
file_config = FileConfig.create() 