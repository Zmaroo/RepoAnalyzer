#!/usr/bin/env python3
"""
Integration Test Template

This file serves as a template for creating new integration tests for the RepoAnalyzer project.
Copy this file and modify it to create your own integration tests.
Remember to name your file according to the convention: test_integration_[module]_[description].py
"""

import os
import sys
import pytest
import tempfile
import shutil
from typing import Dict, List, Any
import numpy as np
from parsers.query_patterns import initialize_pattern_system
from parsers.types import ParserType, FileType, ParserResult
from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor
import asyncio
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
from parsers.language_support import language_registry
from parsers.models import FileClassification
from indexer.file_processor import FileProcessor
from parsers.file_classification import classify_file, FileType, ParserType
# from db.database import Database  # This module doesn't exist
from utils.health_monitor import global_health_monitor, monitor_operation, ComponentStatus
from utils.logger import log
from pathlib import Path
from parsers.unified_parser import unified_parser
from contextlib import asynccontextmanager

# Add the parent directory to the path so we can import the project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules you need to test
from utils.app_init import initialize_application

# Initialize pattern system at module level
initialize_pattern_system()

# Create a mock tree-sitter language pack and pattern processor before importing app_init
mock_language = MagicMock()
mock_parser = MagicMock()
mock_parser.set_language = MagicMock()
mock_tree_sitter_parser = MagicMock()
mock_patterns = {"functions": {}, "classes": {}, "imports": {}}

# Create mocks for the pattern processor
mock_pattern_processor = MagicMock()
mock_pattern_processor.get_patterns_for_file.return_value = mock_patterns

# Create a mock feature extractor
mock_feature_extractor = MagicMock()
mock_feature_extractor.extract_features.return_value = {"features": {}}

# Patch the necessary modules and functions
with patch('tree_sitter_language_pack.get_language', return_value=mock_language):
    with patch('tree_sitter_language_pack.get_parser', return_value=mock_parser):
        with patch('tree_sitter.Parser', return_value=mock_tree_sitter_parser):
            with patch('parsers.pattern_processor.pattern_processor', mock_pattern_processor):
                # Now import after patching
                initialize_application()

# Initialize pattern system at module level
initialize_pattern_system()

# Mock Database class for testing
class Database:
    """Mock Database class for testing"""
    @staticmethod
    async def connect():
        log("Mock database connected")
        return True
        
    @staticmethod
    async def disconnect():
        log("Mock database disconnected")
        return True
        
    @staticmethod
    async def query(query_string, params=None):
        log(f"Mock query executed: {query_string}")
        return []


# Example fixtures - modify as needed for your specific tests
@pytest.fixture
def sample_repo():
    """Create a temporary directory with a sample file."""
    tmp_dir = tempfile.mkdtemp()
    
    # Create a sample Python file
    with open(os.path.join(tmp_dir, "sample.py"), "w") as f:
        f.write("""
def hello_world():
    print("Hello, World!")
    
if __name__ == "__main__":
    hello_world()
""")
    
    yield tmp_dir
    
    # Cleanup
    shutil.rmtree(tmp_dir)


@pytest.fixture
def mock_db():
    """Create a mock database for testing."""
    # You could use a real test database or a mock
    # This example uses a simple in-memory mock
    from unittest.mock import MagicMock
    db = MagicMock()
    db.connect.return_value = True
    db.insert.return_value = True
    db.query.return_value = []
    
    return db


@pytest.fixture
def mock_tree_sitter():
    """Mock tree-sitter components for testing."""
    from unittest.mock import MagicMock, AsyncMock, patch
    from parsers.types import ParserResult, ExtractedFeatures, Documentation, ComplexityMetrics
    
    # Create mock objects
    mock_language = MagicMock()
    mock_parser = MagicMock()
    mock_feature_extractor = MagicMock()
    
    # Set up mock parser
    mock_parser.parse.return_value = MagicMock()
    
    # Create a mock result for parse method
    mock_result = ParserResult(
        success=True,
        ast={"type": "module", "children": []},
        features={},
        documentation={},
        complexity={},
        statistics={}
    )
    
    # Create patches
    with patch('tree_sitter_language_pack.get_language', return_value=mock_language) as mock_get_language, \
         patch('tree_sitter_language_pack.get_parser', return_value=mock_parser) as mock_get_parser, \
         patch('parsers.base_parser.BaseParser._extract_category_features') as mock_extract_category_features, \
         patch('parsers.tree_sitter_parser.TreeSitterParser._parse_source') as mock_parse_source, \
         patch('parsers.base_parser.BaseParser.parse', new_callable=AsyncMock) as mock_parse:
        
        # Configure mocks
        mock_parse_source = AsyncMock(return_value={"type": "module", "children": []})
        mock_extract_category_features.return_value = {}
        mock_parse.return_value = mock_result
        
        # Create a custom _initialize_parser method for TreeSitterFeatureExtractor
        def _initialize_parser(self):
            self._parser = mock_parser
            self._language = mock_language
            self._patterns = {}
        
        # Patch the _initialize_parser method
        with patch('parsers.feature_extractor.TreeSitterFeatureExtractor._initialize_parser', _initialize_parser):
            # Yield all the mocks for use in tests
            yield {
                'language': mock_language,
                'get_language': mock_get_language,
                'get_parser': mock_get_parser,
                'parser': mock_parser,
                'feature_extractor': mock_feature_extractor,
                'extract_category_features': mock_extract_category_features,
                'parse_source': mock_parse_source,
                'parse': mock_parse
            }


# Example test function that tests the integration between file processing and parsing
@pytest.mark.asyncio
async def test_file_processing_and_parsing_integration(sample_repo, mock_tree_sitter):
    """Test that file processing correctly interacts with parsing."""
    from unittest.mock import AsyncMock, patch
    
    # Setup
    file_processor = FileProcessor()
    
    # Mock the database operations
    with patch('indexer.file_processor.upsert_code_snippet', new_callable=AsyncMock) as mock_upsert:
        # Process a file
        python_file = os.path.join(sample_repo, "sample.py")
        # Properly await the async method and provide all required arguments
        # Using 1 as a dummy repo_id and sample_repo as the base_path
        process_result = await file_processor.process_file(python_file, repo_id=1, base_path=sample_repo)
        
        # Verify that file processing was successful
        assert process_result is not None, f"Failed to process {python_file}"
        assert process_result['file_path'] == os.path.relpath(python_file, sample_repo)
        assert process_result['status'] == 'success'
        
        # Verify that upsert_code_snippet was called
        mock_upsert.assert_called_once()


# Example test that involves multiple components
@pytest.mark.asyncio
async def test_end_to_end_processing(sample_repo, mock_db):
    """Test the entire processing pipeline from indexing to database storage."""
    # Set up the parse_result
    mock_parse_result = ParserResult(
        success=True,
        ast={"type": "module", "children": []},
        features={"syntax": {}, "semantics": {}},
        documentation={},
        complexity={},
        statistics={}
    )

    # Mock unified_parser.parse_file to return a successful result
    mock_parse_file = AsyncMock(return_value=mock_parse_result)

    # Mock the embedding function
    mock_embed = AsyncMock()
    mock_embed.return_value = np.array([0.1] * 768)  # Return a numpy array with tolist method

    # Mock cached versions of functions
    cached_parse_file_mock = AsyncMock(return_value=mock_parse_result)
    cached_embed_code_mock = AsyncMock(return_value=mock_embed.return_value)
    cached_read_file_mock = AsyncMock(return_value='mock content')
    cached_get_patterns_mock = AsyncMock(return_value={})
    cached_classify_file_mock = AsyncMock(return_value=FileClassification(
        file_type=FileType.CODE,
        language_id='python',
        parser_type=ParserType.TREE_SITTER,
        file_path='',
        is_binary=False
    ))

    # Create a simple mock for upsert_code_snippet
    mock_upsert = AsyncMock()

    # Mock the AsyncErrorBoundary context manager to just yield without any error handling
    @asynccontextmanager
    async def mock_async_error_boundary(*args, **kwargs):
        yield

    with patch('db.upsert_ops.upsert_code_snippet', mock_upsert), \
         patch('parsers.unified_parser.unified_parser.parse_file', mock_parse_file), \
         patch('indexer.common.async_read_file', cached_read_file_mock), \
         patch('parsers.file_classification.classify_file', return_value=cached_classify_file_mock.return_value), \
         patch('embedding.embedding_models.code_embedder.embed_code', mock_embed), \
         patch('indexer.file_processor.cached_read_file', cached_read_file_mock), \
         patch('indexer.file_processor.cached_classify_file', cached_classify_file_mock), \
         patch('indexer.file_processor.cached_parse_file', cached_parse_file_mock), \
         patch('indexer.file_processor.cached_embed_code', cached_embed_code_mock), \
         patch('indexer.file_processor.cached_get_patterns', cached_get_patterns_mock), \
         patch('indexer.file_utils.get_file_classification', return_value=cached_classify_file_mock.return_value), \
         patch('indexer.file_utils.get_relative_path', return_value='sample.py'), \
         patch('utils.error_handling.AsyncErrorBoundary', mock_async_error_boundary):

        # Start health monitoring for the test
        with monitor_operation("end_to_end", "integration_test"):
            # Setup
            file_processor = FileProcessor()

            # Process all files in the sample repo
            processed_files = []
            for root, _, files in os.walk(sample_repo):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Process file is a coroutine - we need to await it
                    result = await file_processor.process_file(file_path, repo_id=1, base_path=sample_repo)
                    processed_files.append(result)

            # Verify all files were processed
            assert len(processed_files) > 0, "No files were processed"
            assert all(result is not None for result in processed_files), "Not all files were processed successfully"
            
            # Verify that upsert_code_snippet was called at least once
            mock_upsert.assert_called()


# You can add more test functions below
# def test_another_integration_scenario():
#     """Description of what this test is verifying."""
#     pass


if __name__ == "__main__":
    # This allows you to run this test file directly
    pytest.main(["-xvs", __file__]) 