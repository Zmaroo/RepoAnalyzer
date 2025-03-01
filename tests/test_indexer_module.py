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
from indexer.repo_indexer import RepositoryIndexer
from indexer.file_indexer import FileIndexer
from indexer.folder_indexer import FolderIndexer
from indexer.language_indexer import LanguageIndexer
from indexer.pattern_indexer import PatternIndexer
from indexer.code_scanner import CodeScanner
from indexer.types import (
    FileInfo,
    FolderInfo,
    IndexingOptions,
    IndexingResult
)
from parsers.types import (
    ParserResult,
    CodePattern,
    ParserPayload
)


class TestFileIndexer:
    """Test file indexing functionality."""
    
    @pytest.fixture
    def sample_file_content(self):
        """Sample file content for testing."""
        return """
        def hello_world():
            print("Hello, world!")
            return 42
        
        class TestClass:
            def __init__(self):
                self.value = 100
                
            def get_value(self):
                return self.value
        """
    
    @pytest.fixture
    def temp_file(self, sample_file_content):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            tmp.write(sample_file_content.encode())
            tmp_path = tmp.name
        
        yield tmp_path
        
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_index_file(self, temp_file):
        """Test indexing a file."""
        # Create mocks
        mock_parser = AsyncMock()
        mock_pattern_indexer = AsyncMock()
        mock_db = AsyncMock()
        
        # Setup parser mock
        mock_parser_result = ParserResult(
            language="python",
            patterns=[
                CodePattern(
                    type="function",
                    name="hello_world",
                    start_line=2,
                    end_line=4,
                    content="def hello_world():\n    print(\"Hello, world!\")\n    return 42",
                    metadata={}
                ),
                CodePattern(
                    type="class",
                    name="TestClass",
                    start_line=6,
                    end_line=12,
                    content="class TestClass:\n    def __init__(self):\n        self.value = 100\n        \n    def get_value(self):\n        return self.value",
                    metadata={}
                )
            ],
            imports=[],
            metrics={"function_count": 2, "class_count": 1}
        )
        mock_parser.parse_file.return_value = mock_parser_result
        
        # Create the file indexer
        indexer = FileIndexer(
            parser=mock_parser,
            pattern_indexer=mock_pattern_indexer,
            db=mock_db
        )
        
        # Index the file
        file_info = FileInfo(
            path=temp_file,
            repo_id="test_repo_id",
            relative_path="test.py"
        )
        result = await indexer.index_file(file_info)
        
        # Verify the indexer called the parser
        mock_parser.parse_file.assert_called_once_with(temp_file)
        
        # Verify the result
        assert result.success is True
        assert result.language == "python"
        assert result.pattern_count == 2
        assert "function_count" in result.metrics
        assert result.metrics["function_count"] == 2
    
    @pytest.mark.asyncio
    async def test_file_indexing_failure(self):
        """Test handling of file indexing failures."""
        # Create mocks
        mock_parser = AsyncMock()
        mock_pattern_indexer = AsyncMock()
        mock_db = AsyncMock()
        
        # Setup parser mock to fail
        mock_parser.parse_file.side_effect = Exception("Parsing failed")
        
        # Create the file indexer
        indexer = FileIndexer(
            parser=mock_parser,
            pattern_indexer=mock_pattern_indexer,
            db=mock_db
        )
        
        # Create a non-existent file
        file_info = FileInfo(
            path="/non/existent/file.py",
            repo_id="test_repo_id",
            relative_path="file.py"
        )
        
        # Index the file
        result = await indexer.index_file(file_info)
        
        # Verify the result indicates failure
        assert result.success is False
        assert result.error is not None


class TestFolderIndexer:
    """Test folder indexing functionality."""
    
    @pytest.fixture
    def temp_folder(self):
        """Create a temporary folder structure for testing."""
        # Create temporary folder
        temp_dir = tempfile.mkdtemp()
        
        # Create some files and subdirectories
        python_file = os.path.join(temp_dir, "main.py")
        with open(python_file, "w") as f:
            f.write("def main():\n    print('Hello, world!')")
        
        # Create a subdirectory
        sub_dir = os.path.join(temp_dir, "lib")
        os.makedirs(sub_dir)
        
        # Create a file in the subdirectory
        sub_file = os.path.join(sub_dir, "utils.py")
        with open(sub_file, "w") as f:
            f.write("def util_func():\n    return True")
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_index_folder(self, temp_folder):
        """Test indexing a folder."""
        # Create mocks
        mock_file_indexer = AsyncMock()
        mock_db = AsyncMock()
        
        # Setup file indexer mock
        mock_file_indexer.index_file.return_value = IndexingResult(
            success=True,
            language="python",
            pattern_count=1,
            metrics={"function_count": 1}
        )
        
        # Create the folder indexer
        indexer = FolderIndexer(
            file_indexer=mock_file_indexer,
            db=mock_db
        )
        
        # Index the folder
        folder_info = FolderInfo(
            path=temp_folder,
            repo_id="test_repo_id",
            relative_path=""
        )
        result = await indexer.index_folder(folder_info)
        
        # Verify the result
        assert result.success is True
        assert result.file_count >= 2  # At least 2 files (main.py and lib/utils.py)
        assert result.folder_count >= 1  # At least 1 folder (lib)
        
        # Verify the file indexer was called for each file
        assert mock_file_indexer.index_file.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_folder_exclusion(self, temp_folder):
        """Test excluding folders during indexing."""
        # Create a .git directory that should be excluded
        git_dir = os.path.join(temp_folder, ".git")
        os.makedirs(git_dir)
        git_file = os.path.join(git_dir, "HEAD")
        with open(git_file, "w") as f:
            f.write("ref: refs/heads/main")
        
        # Create mocks
        mock_file_indexer = AsyncMock()
        mock_db = AsyncMock()
        
        # Setup file indexer mock
        mock_file_indexer.index_file.return_value = IndexingResult(
            success=True,
            language="python",
            pattern_count=1,
            metrics={"function_count": 1}
        )
        
        # Create the folder indexer with exclusion patterns
        indexer = FolderIndexer(
            file_indexer=mock_file_indexer,
            db=mock_db,
            exclude_patterns=[".git", "__pycache__", "node_modules"]
        )
        
        # Index the folder
        folder_info = FolderInfo(
            path=temp_folder,
            repo_id="test_repo_id",
            relative_path=""
        )
        result = await indexer.index_folder(folder_info)
        
        # The .git directory should be excluded
        for call in mock_file_indexer.index_file.call_args_list:
            file_info = call[0][0]
            assert ".git" not in file_info.path


class TestRepositoryIndexer:
    """Test repository indexing functionality."""
    
    @pytest.fixture
    def mock_repo_db(self):
        """Create a mock repository database."""
        mock_db = AsyncMock()
        mock_db.get_repository_by_url.return_value = {
            "id": "test_repo_id",
            "url": "https://github.com/test/repo",
            "name": "repo"
        }
        mock_db.store_repository.return_value = {
            "id": "new_repo_id",
            "url": "https://github.com/test/new-repo",
            "name": "new-repo"
        }
        return mock_db
    
    @pytest.fixture
    def mock_folder_indexer(self):
        """Create a mock folder indexer."""
        mock_indexer = AsyncMock()
        mock_indexer.index_folder.return_value = IndexingResult(
            success=True,
            file_count=10,
            folder_count=5,
            metrics={"function_count": 20, "class_count": 5}
        )
        return mock_indexer
    
    @pytest.mark.asyncio
    async def test_index_existing_repository(self, mock_repo_db, mock_folder_indexer, temp_folder):
        """Test indexing an existing repository."""
        # Create the repository indexer
        indexer = RepositoryIndexer(
            repo_db=mock_repo_db,
            folder_indexer=mock_folder_indexer
        )
        
        # Index an existing repository
        repo_url = "https://github.com/test/repo"
        repo_dir = temp_folder
        result = await indexer.index_repository(repo_url, repo_dir)
        
        # Verify the result
        assert result.success is True
        assert result.repo_id == "test_repo_id"
        assert result.file_count == 10
        assert result.folder_count == 5
        
        # Verify the database was called
        mock_repo_db.get_repository_by_url.assert_called_once_with(repo_url)
        mock_repo_db.store_repository.assert_not_called()
        
        # Verify the folder indexer was called
        mock_folder_indexer.index_folder.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_index_new_repository(self, mock_repo_db, mock_folder_indexer, temp_folder):
        """Test indexing a new repository."""
        # Setup database mock for a new repository
        mock_repo_db.get_repository_by_url.return_value = None
        
        # Create the repository indexer
        indexer = RepositoryIndexer(
            repo_db=mock_repo_db,
            folder_indexer=mock_folder_indexer
        )
        
        # Index a new repository
        repo_url = "https://github.com/test/new-repo"
        repo_dir = temp_folder
        result = await indexer.index_repository(repo_url, repo_dir)
        
        # Verify the result
        assert result.success is True
        assert result.repo_id == "new_repo_id"
        assert result.file_count == 10
        assert result.folder_count == 5
        
        # Verify the database was called
        mock_repo_db.get_repository_by_url.assert_called_once_with(repo_url)
        mock_repo_db.store_repository.assert_called_once()
        
        # Verify the folder indexer was called
        mock_folder_indexer.index_folder.assert_called_once()


class TestCodeScanner:
    """Test code scanning functionality."""
    
    @pytest.fixture
    def sample_code(self):
        """Sample code for testing."""
        return """
        import os
        import sys
        
        def read_file(filename):
            with open(filename, 'r') as f:
                return f.read()
        
        def write_file(filename, content):
            with open(filename, 'w') as f:
                f.write(content)
        
        class FileHandler:
            def __init__(self, base_dir='.'):
                self.base_dir = base_dir
                
            def get_full_path(self, filename):
                return os.path.join(self.base_dir, filename)
                
            def read(self, filename):
                return read_file(self.get_full_path(filename))
                
            def write(self, filename, content):
                write_file(self.get_full_path(filename), content)
        """
    
    @pytest.mark.asyncio
    async def test_scan_code(self, sample_code):
        """Test scanning code for patterns."""
        # Create the code scanner
        scanner = CodeScanner()
        
        # Scan the code
        patterns = await scanner.scan_code(sample_code, language="python")
        
        # Verify the patterns
        assert len(patterns) > 0
        
        # Check for functions
        function_patterns = [p for p in patterns if p.type == "function"]
        assert len(function_patterns) >= 2  # At least read_file and write_file
        
        # Check for classes
        class_patterns = [p for p in patterns if p.type == "class"]
        assert len(class_patterns) >= 1  # At least FileHandler
        
        # Check for imports
        import_patterns = [p for p in patterns if p.type == "import"]
        assert len(import_patterns) >= 2  # At least os and sys
    
    @pytest.mark.asyncio
    async def test_find_related_patterns(self, sample_code):
        """Test finding relationships between code patterns."""
        # Create the code scanner
        scanner = CodeScanner()
        
        # Scan the code first
        patterns = await scanner.scan_code(sample_code, language="python")
        
        # Find relationships between patterns
        related_patterns = await scanner.find_related_patterns(patterns)
        
        # Verify relationships exist
        assert len(related_patterns) > 0
        
        # Find FileHandler class and its methods
        file_handler_class = next((p for p in patterns if p.type == "class" and p.name == "FileHandler"), None)
        assert file_handler_class is not None
        
        # Check that class methods are related to the class
        class_methods = [r for r in related_patterns if r[0] == file_handler_class.id]
        assert len(class_methods) >= 3  # __init__, get_full_path, read, write
        
        # Find read method and check that it calls read_file function
        read_method = next((p for p in patterns if p.type == "method" and p.name == "read"), None)
        read_file_func = next((p for p in patterns if p.type == "function" and p.name == "read_file"), None)
        
        if read_method and read_file_func:
            read_calls = [r for r in related_patterns if r[0] == read_method.id and r[1] == read_file_func.id]
            assert len(read_calls) > 0 