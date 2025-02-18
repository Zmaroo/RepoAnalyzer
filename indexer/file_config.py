from dataclasses import dataclass, field
from typing import Set
from parsers.language_mapping import (
    FileClassification,
    get_file_classification,
    FileType
)

@dataclass(frozen=True)
class FileConfig:
    """Central configuration for file handling."""
    binary_extensions: Set[str] = field(default_factory=lambda: {
        '.pdf', '.jpg', '.png', '.gif', '.ico', '.svg',
        '.woff', '.woff2', '.ttf', '.eot',
        '.zip', '.tar', '.gz', '.rar',
        '.exe', '.dll', '.so', '.dylib',
        '.pyc', '.pyo', '.pyd'
    })
    
    @classmethod
    def create(cls) -> 'FileConfig':
        """Create a new FileConfig instance."""
        return cls()
    
    def is_processable(self, file_path: str) -> bool:
        """Check if a file should be processed."""
        from indexer.file_utils import is_binary_file
        from indexer.file_ignore_config import IGNORED_FILES
        
        classification = get_file_classification(file_path)
        return (
            classification is not None and
            classification.file_type in (FileType.CODE, FileType.DOC) and
            not any(file_path.endswith(pat) for pat in IGNORED_FILES) and
            not is_binary_file(file_path)
        ) 