"""Integration tests for AST caching functionality."""

import asyncio
import unittest
import hashlib
from unittest.mock import patch, MagicMock
from parsers.tree_sitter_parser import TreeSitterParser
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from parsers.types import FileType, ParserType
from utils.cache import cache_coordinator

class TestASTCache(unittest.TestCase):
    """Test cases for AST caching."""
    
    def setUp(self):
        """Set up the test case."""
        # Clear cache before each test
        asyncio.run(cache_coordinator.ast_cache.clear_async())
        
        # Choose a language that's widely supported
        self.parser = TreeSitterParser("python", FileType.CODE)
        self.parser.initialize()
        
        # Sample Python code
        self.sample_code = """
def hello_world():
    print("Hello, world!")
    
hello_world()
"""
        self.code_hash = hashlib.md5(self.sample_code.encode('utf8')).hexdigest()
        self.cache_key = f"ast:python:{self.code_hash}"
    
    def test_ast_caching(self):
        """Test that ASTs are properly cached."""
        # First parse should miss cache
        with patch('utils.cache.ast_cache.get_async') as mock_get:
            mock_get.return_value = None
            with patch('utils.cache.ast_cache.set_async') as mock_set:
                # Parse the code
                ast = self.parser._parse_source(self.sample_code)
                
                # Verify the cache was checked
                mock_get.assert_called_once()
                
                # Verify the result was cached
                mock_set.assert_called_once()
                
                # Verify we got a valid AST with a root node
                self.assertIn("root", ast)
                self.assertIn("tree", ast)
    
    def test_ast_cache_hit(self):
        """Test that cached ASTs are retrieved properly."""
        # First, populate the cache
        ast1 = self.parser._parse_source(self.sample_code)
        
        # Now patch only the get method to verify it would be called
        with patch('utils.cache.ast_cache.get_async') as mock_get:
            # Simulate a cache hit by returning a mock AST structure
            mock_cached_ast = {"tree": {"type": "module", "children": []}}
            mock_get.return_value = mock_cached_ast
            
            # Second parse should hit cache
            ast2 = self.parser._parse_source(self.sample_code)
            
            # Verify the cache was checked
            mock_get.assert_called_once()
            
            # Verify the cached result was used
            self.assertEqual(ast2["tree"], mock_cached_ast["tree"])
    
    def test_pattern_processing_with_cached_ast(self):
        """Test that pattern processing works with a cached AST."""
        # Create a simplified mock pattern
        mock_pattern = MagicMock()
        mock_pattern.pattern_name = "(function_definition) @function"
        
        # First, parse without caching to get a complete AST
        ast1 = self.parser._parse_source(self.sample_code)
        
        # Verify we can process patterns on the full AST
        matches1 = self.parser._process_pattern(ast1, self.sample_code, mock_pattern)
        
        # Now create a cached version with only the tree (no root node)
        cached_ast = {"tree": ast1["tree"]}
        
        # Process pattern on the cached AST - should regenerate the root node
        matches2 = self.parser._process_pattern(cached_ast, self.sample_code, mock_pattern)
        
        # Both should find the function definition
        self.assertTrue(len(matches1) > 0, "Expected to find pattern matches with full AST")
        self.assertTrue(len(matches2) > 0, "Expected to find pattern matches with cached AST")

if __name__ == "__main__":
    unittest.main() 