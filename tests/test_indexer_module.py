#!/usr/bin/env python3
"""
Unit tests for indexer modules.

This module tests the indexer functionality in the RepoAnalyzer project:
1. Repository scanning and indexing
2. File and folder management
3. Code analysis and pattern recognition
4. Graph model generation
"""

import os
import sys
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import indexer modules
from indexer.file_processor import FileProcessor
from indexer.file_utils import get_file_classification, get_files, get_relative_path, is_processable_file
from indexer.unified_indexer import index_active_project, index_active_project_sync, process_repository_indexing
from indexer.common import async_read_file, async_handle_errors
from indexer.async_utils import batch_process_files
from indexer.clone_and_index import clone_and_index_repo, get_or_create_repo
from parsers.models import FileClassification
from parsers.types import FileType, ParserType

# Define types that we need for the tests
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Union

@dataclass
class FileInfo:
    """File information structure for tests."""
    path: str
    language: str
    file_type: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class FolderInfo:
    """Folder information structure for tests."""
    path: str
    files: List[FileInfo] = field(default_factory=list)
    subfolders: List['FolderInfo'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IndexingOptions:
    """Options for indexing operations."""
    exclude_dirs: List[str] = field(default_factory=list)
    exclude_files: List[str] = field(default_factory=list)
    include_extensions: List[str] = field(default_factory=list)
    
@dataclass
class IndexingResult:
    """Result of an indexing operation."""
    success: bool
    files_processed: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# Updated test classes to use the correct modules

class TestFileProcessor:
    """Tests for the FileProcessor class."""
    
    @pytest.fixture
    def sample_file_content(self):
        """Fixture that provides sample file content for testing."""
        return """
        def hello_world():
            print("Hello, World!")
            
        class TestClass:
            def __init__(self, name):
                self.name = name
                
            def greet(self):
                return f"Hello, {self.name}!"
        """
    
    @pytest.fixture
    def temp_file(self, sample_file_content):
        """Fixture that creates a temporary file for testing."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create a temporary file with sample content
        file_path = os.path.join(temp_dir, "test_file.py")
        with open(file_path, 'w') as f:
            f.write(sample_file_content)
            
        yield file_path
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_process_file(self, temp_file):
        """Test processing a file."""
        # Create mock db methods and patch them
        with patch('db.upsert_ops.upsert_code_snippet', new_callable=AsyncMock) as mock_upsert:
            # Create a FileProcessor instance (no db_client parameter)
            processor = FileProcessor()
            
            # Process the file
            with patch('indexer.file_processor.get_relative_path', return_value="test_file.py"):
                with patch('indexer.file_processor.async_read_file', new_callable=AsyncMock) as mock_read:
                    mock_read.return_value = "def test(): pass"
                    result = await processor.process_file(temp_file, repo_id=1, base_path="/test")
            
            # Assertions
            assert result is not None
            
    @pytest.mark.asyncio
    async def test_file_processing_failure(self):
        """Test handling of file processing failures."""
        # Create a FileProcessor instance
        processor = FileProcessor()
        
        # Process a non-existent file
        with patch('indexer.file_processor.async_read_file', side_effect=Exception("File not found")):
            result = await processor.process_file("non_existent_file.py", repo_id=1, base_path="/test")
        
        # Assertions
        assert result is None

class TestFileUtils:
    """Tests for the file utility functions."""
    
    @pytest.fixture
    def temp_folder(self):
        """Fixture that creates a temporary folder structure for testing."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create some subdirectories
        os.makedirs(os.path.join(temp_dir, "src"))
        os.makedirs(os.path.join(temp_dir, "docs"))
        os.makedirs(os.path.join(temp_dir, "tests"))
        os.makedirs(os.path.join(temp_dir, ".git"))
        
        # Create some files
        with open(os.path.join(temp_dir, "src", "main.py"), 'w') as f:
            f.write("print('Hello, World!')")
            
        with open(os.path.join(temp_dir, "docs", "README.md"), 'w') as f:
            f.write("# Test Project")
            
        with open(os.path.join(temp_dir, "tests", "test_main.py"), 'w') as f:
            f.write("def test_main(): pass")
            
        with open(os.path.join(temp_dir, ".git", "config"), 'w') as f:
            f.write("[core]\n\trepositoryformatversion = 0")
            
        yield temp_dir
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_get_files(self, temp_folder):
        """Test getting files from a directory."""
        # Get all files
        files = get_files(temp_folder)
        
        # Assertions
        assert len(files) >= 3  # At least 3 files created in the fixture
        assert any(f.endswith("main.py") for f in files)
        assert any(f.endswith("README.md") for f in files)
        assert any(f.endswith("test_main.py") for f in files)
        
        # Test with exclusions
        files_excluding_git = get_files(temp_folder, exclude_dirs=[".git"])
        assert not any(".git" in f for f in files_excluding_git)
    
    def test_get_file_classification(self):
        """Test file classification based on extension."""
        # Since we can't easily test with actual files, we'll mock the function
        with patch('indexer.file_utils.is_binary_file', return_value=False):
            with patch('parsers.file_classification.classify_file') as mock_classify:
                # Create a mock classification
                mock_classification = FileClassification(
                    file_path="test.py",
                    language_id="python",
                    parser_type=ParserType.TREE_SITTER,
                    file_type=FileType.CODE
                )
                mock_classify.return_value = mock_classification
                
                # Test
                result = get_file_classification("test.py")
                
                # Verify it returns the FileClassification object
                assert result is mock_classification
                assert result.language_id == "python"
                assert result.file_type == FileType.CODE
    
    def test_is_processable_file(self):
        """Test file processability check."""
        # Since the function depends on other functions, we'll mock them
        with patch('indexer.file_utils.is_binary_file', return_value=False):
            with patch('indexer.file_utils.should_ignore', return_value=False):
                # Test
                result = is_processable_file("main.py")
                assert result is True
                
                # Test with binary file
                with patch('indexer.file_utils.is_binary_file', return_value=True):
                    result = is_processable_file("image.jpg")
                    assert result is False

class TestUnifiedIndexer:
    """Tests for the unified indexing functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Fixture that provides a mock database client."""
        mock = AsyncMock()
        mock.store_repository_data = AsyncMock()
        mock.store_file_data = AsyncMock()
        mock.get_repository = AsyncMock(return_value=None)
        return mock
    
    @pytest.fixture
    def mock_file_processor(self):
        """Fixture that provides a mock file processor."""
        mock = AsyncMock()
        mock.process_file = AsyncMock(return_value={"success": True})
        return mock
        
    @pytest.fixture
    def temp_folder(self):
        """Fixture that creates a temporary folder structure for testing."""
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create some subdirectories
        os.makedirs(os.path.join(temp_dir, "src"))
        os.makedirs(os.path.join(temp_dir, "docs"))
        
        # Create some files
        with open(os.path.join(temp_dir, "src", "main.py"), 'w') as f:
            f.write("print('Hello, World!')")
            
        with open(os.path.join(temp_dir, "docs", "README.md"), 'w') as f:
            f.write("# Test Project")
            
        yield temp_dir
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_index_active_project(self, mock_db, mock_file_processor, temp_folder):
        """Test indexing a project."""
        # Patch various functions to avoid actual DB calls and file processing
        with patch('db.neo4j_ops.get_or_create_repo', return_value=1):
            with patch('indexer.unified_indexer.ProcessingCoordinator') as mock_coordinator:
                coordinator_instance = mock_coordinator.return_value
                coordinator_instance.process_file = mock_file_processor.process_file
                
                # Patch get_files to return our test files
                with patch('indexer.unified_indexer.get_files', return_value=[
                    os.path.join(temp_folder, "src", "main.py"),
                    os.path.join(temp_folder, "docs", "README.md")
                ]):
                    # Run the function with the temp folder as a fake repo
                    result = await process_repository_indexing(
                        repo_path=temp_folder,
                        repo_id=1
                    )
                    
                    # Check that the function completed
                    assert coordinator_instance.process_file.called
    
    @pytest.mark.asyncio
    async def test_process_repository_indexing(self, mock_db, temp_folder):
        """Test repository indexing process."""
        # Patch database operations and file processing
        with patch('db.neo4j_ops.get_or_create_repo', return_value=1):
            with patch('indexer.unified_indexer.ProcessingCoordinator') as mock_coordinator:
                coordinator_instance = mock_coordinator.return_value
                coordinator_instance.process_file.return_value = {"success": True}
                
                # Patch get_files to return our test files
                with patch('indexer.unified_indexer.get_files', return_value=[
                    os.path.join(temp_folder, "src", "main.py"),
                    os.path.join(temp_folder, "docs", "README.md")
                ]):
                    # Run the function
                    result = await process_repository_indexing(
                        repo_path=temp_folder,
                        repo_id=1
                    )
                    
                    # Verify the coordinator was used
                    mock_coordinator.assert_called_once()
                    coordinator_instance.cleanup.assert_called_once()

# Other test classes can be added for clone_and_index, async_utils, etc. 