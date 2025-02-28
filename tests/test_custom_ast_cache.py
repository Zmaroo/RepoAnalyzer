"""Integration tests for AST caching in BaseParser."""

import asyncio
import unittest
import hashlib
from unittest.mock import patch, MagicMock, call, AsyncMock
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, ParserResult
from utils.cache import ast_cache

class TestParser(BaseParser):
    """Concrete implementation of BaseParser for testing."""
    
    def __init__(self, language_id="test_lang", file_type=FileType.CODE):
        super().__init__(language_id, file_type, ParserType.CUSTOM)
        self._initialized = True
    
    def initialize(self) -> bool:
        """Initialize the parser."""
        self._initialized = True
        return True
    
    def _parse_source(self, source_code):
        """Parse the source code."""
        ast = {"type": "document", "children": []}
        return ast

class MockFeatureResult:
    """Mock feature extraction result."""
    def __init__(self):
        self.features = {}
        self.documentation = type('obj', (object,), {'__dict__': {}})
        self.metrics = type('obj', (object,), {'__dict__': {}})

class TestBaseParserCaching(unittest.TestCase):
    """Test cases for AST caching in BaseParser."""
    
    def setUp(self):
        """Set up the test case."""
        # Clear cache before each test
        asyncio.run(ast_cache.clear_async())
        
        # Sample code content
        self.sample_code = "Sample code for testing"
        self.code_hash = hashlib.md5(self.sample_code.encode('utf8')).hexdigest()
        
        # Create a concrete parser instance with mocked feature extractor
        with patch('parsers.feature_extractor.CustomFeatureExtractor') as MockExtractor:
            # Set up mock feature extractor
            mock_extractor = MockExtractor.return_value
            mock_extractor.extract_features.return_value = MockFeatureResult()
            
            # Create the parser
            self.parser = TestParser("test_lang", FileType.CODE)
            
            # Replace the feature extractor with our mock
            self.parser.feature_extractor = mock_extractor
        
        # Configure the cache key format
        self.cache_key = f"ast:test_lang:{self.code_hash}"
    
    def test_parse_with_cache_miss(self):
        """Test parsing a source file with cache miss."""
        # Mock AST to be returned by _parse_source
        mock_ast = {"type": "document", "children": []}
        
        # Patch the relevant methods
        with patch.object(self.parser, '_check_ast_cache') as mock_check_cache:
            # Simulate cache miss
            mock_check_cache.return_value = None
            
            with patch.object(self.parser, '_parse_source') as mock_parse:
                # Set up _parse_source to return a valid AST
                mock_parse.return_value = mock_ast
                
                with patch.object(self.parser, '_store_ast_in_cache') as mock_store_cache:
                    # Call the parser
                    result = self.parser.parse(self.sample_code)
                    
                    # Verify the expected interactions
                    mock_check_cache.assert_called_once()
                    mock_parse.assert_called_once_with(self.sample_code)
                    mock_store_cache.assert_called_once_with(self.sample_code, mock_ast)
                    
                    # Verify result contains the expected AST
                    self.assertIsNotNone(result)
                    self.assertEqual(result.ast, mock_ast)
                    self.assertTrue(result.success)
    
    def test_parse_with_cache_hit(self):
        """Test parsing a source file with cache hit."""
        # Mock cached AST
        mock_ast = {"type": "document", "children": []}
        
        # Patch the relevant methods
        with patch.object(self.parser, '_check_ast_cache') as mock_check_cache:
            # Simulate cache hit
            mock_check_cache.return_value = mock_ast
            
            with patch.object(self.parser, '_parse_source') as mock_parse:
                with patch.object(self.parser, '_store_ast_in_cache') as mock_store_cache:
                    # Call the parser
                    result = self.parser.parse(self.sample_code)
                    
                    # Verify the expected interactions
                    mock_check_cache.assert_called_once()
                    mock_parse.assert_not_called()  # Should not parse from scratch
                    mock_store_cache.assert_not_called()  # Should not store again
                    
                    # Verify result contains the cached AST
                    self.assertIsNotNone(result)
                    self.assertEqual(result.ast, mock_ast)
                    self.assertTrue(result.success)
    
    def test_real_cache_storage_and_retrieval(self):
        """Test actual cache storage and retrieval with real Redis."""
        # Create a simple AST to cache
        test_ast = {"type": "test_node", "value": "test"}
        
        # Manually set in cache
        asyncio.run(ast_cache.set_async(self.cache_key, test_ast))
        
        # Test retrieval from actual cache
        with patch.object(self.parser, '_parse_source') as mock_parse:
            # Parse method should retrieve from cache
            result = self.parser.parse(self.sample_code)
            
            # Verify parser didn't call parse_source
            mock_parse.assert_not_called()
            
            # Verify correct AST was retrieved
            self.assertIsNotNone(result)
            self.assertEqual(result.ast["type"], test_ast["type"])
            self.assertEqual(result.ast["value"], test_ast["value"])

if __name__ == "__main__":
    unittest.main() 