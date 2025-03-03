"""Unit tests for the BaseParser class."""

import sys
import os
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any, List, Optional

# Add the parent directory to the path so we can import the project modules properly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, ParserResult, ParserConfig, ParsingStatistics
from parsers.models import PatternType, QueryPattern
from parsers.feature_extractor import TreeSitterFeatureExtractor, CustomFeatureExtractor


class ConcreteParser(BaseParser):
    """Concrete implementation of BaseParser for testing abstract class."""
    
    def __init__(self, language_id="python", file_type=FileType.CODE):
        self.language_id = language_id
        self.file_type = file_type
        self.parser_type = ParserType.TREE_SITTER
        self._initialized = False
        self.__post_init__()
    
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Concrete implementation of abstract method."""
        return {
            "type": "module",
            "children": [
                {
                    "type": "function_definition",
                    "start_point": [1, 0],
                    "end_point": [3, 8],
                    "children": [],
                    "metadata": {"name": "test_function"}
                }
            ],
            "start_point": [0, 0],
            "end_point": [10, 0],
            "errors": []
        }
    
    def _process_pattern(self, pattern: QueryPattern, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Concrete implementation of abstract method."""
        return [
            {
                "type": PatternType.CODE,
                "pattern_name": pattern.name,
                "match": "def test_function():",
                "start_point": [1, 0],
                "end_point": [1, 20],
                "metadata": {"name": "test_function"}
            }
        ]
    
    def initialize(self) -> bool:
        """Concrete implementation of initialize method."""
        self._initialized = True
        return self._initialized


@pytest.fixture
def parser():
    """Fixture that provides a concrete parser instance."""
    return ConcreteParser()


@pytest.fixture
def mock_ast_cache():
    """Fixture that provides a mocked AST cache."""
    with patch('parsers.cache.ast_cache') as mock:
        mock.get_ast = AsyncMock()
        mock.store_ast = AsyncMock()
        yield mock


@pytest.fixture
def sample_ast():
    """Fixture that provides a sample AST for testing."""
    return {
        "type": "module",
        "children": [
            {
                "type": "function_definition",
                "start_point": [1, 0],
                "end_point": [3, 8],
                "children": [],
                "metadata": {"name": "test_function"}
            }
        ],
        "start_point": [0, 0],
        "end_point": [10, 0],
        "errors": [
            {
                "type": "syntax_error",
                "message": "Invalid syntax",
                "line": 5,
                "column": 10
            }
        ]
    }


@pytest.mark.asyncio
class TestBaseParser:
    """Tests for BaseParser class functionality."""
    
    async def test_get_syntax_errors(self, parser, sample_ast):
        """Test extraction of syntax errors from AST."""
        errors = parser._get_syntax_errors(sample_ast)
        
        # Verify that the error from the sample AST was correctly extracted
        assert len(errors) == 1
        assert errors[0]["type"] == "syntax_error"
        assert errors[0]["message"] == "Invalid syntax"
        assert errors[0]["line"] == 5
        assert errors[0]["column"] == 10
        
        # Test with AST that has no errors
        ast_no_errors = sample_ast.copy()
        ast_no_errors["errors"] = []
        errors = parser._get_syntax_errors(ast_no_errors)
        assert len(errors) == 0
    
    async def test_check_ast_cache_hit(self, parser, mock_ast_cache, sample_ast):
        """Test AST cache check when there's a cache hit."""
        mock_ast_cache.get_ast.return_value = sample_ast
        
        result = await parser._check_ast_cache("def test_function():\n    pass")
        
        mock_ast_cache.get_ast.assert_called_once()
        assert result == sample_ast
    
    async def test_check_ast_cache_miss(self, parser, mock_ast_cache):
        """Test AST cache check when there's a cache miss."""
        mock_ast_cache.get_ast.return_value = None
        
        result = await parser._check_ast_cache("def test_function():\n    pass")
        
        mock_ast_cache.get_ast.assert_called_once()
        assert result is None
    
    async def test_store_ast_in_cache(self, parser, mock_ast_cache, sample_ast):
        """Test storing AST in cache."""
        source_code = "def test_function():\n    pass"
        
        await parser._store_ast_in_cache(source_code, sample_ast)
        
        mock_ast_cache.store_ast.assert_called_once_with(
            parser.language_id, 
            parser.file_type, 
            source_code, 
            sample_ast
        )
    
    async def test_parse_with_cache_hit(self, parser, mock_ast_cache, sample_ast):
        """Test parsing when AST is in cache."""
        source_code = "def test_function():\n    pass"
        mock_ast_cache.get_ast.return_value = sample_ast
        
        # Mock feature extractor
        parser.feature_extractor = MagicMock()
        parser.feature_extractor.extract_features.return_value = {"features": {"functions": 1}}
        
        result = await parser.parse(source_code)
        
        # Verify that the parser correctly used the cached AST
        mock_ast_cache.get_ast.assert_called_once()
        assert isinstance(result, ParserResult)
        assert result.ast == sample_ast
        assert result.features == {"features": {"functions": 1}}
        assert len(result.errors) == 1  # From the sample_ast
        
        # Verify internal parsing was not called
        # Since we're using a concrete implementation, we can't patch _parse_source directly
        # Instead we check that the result is based on the cache
        mock_ast_cache.store_ast.assert_not_called()
    
    async def test_parse_with_cache_miss(self, parser, mock_ast_cache):
        """Test parsing when AST is not in cache."""
        source_code = "def test_function():\n    pass"
        mock_ast_cache.get_ast.return_value = None
        
        # Mock feature extractor
        parser.feature_extractor = MagicMock()
        parser.feature_extractor.extract_features.return_value = {"features": {"functions": 1}}
        
        result = await parser.parse(source_code)
        
        # Verify cache interaction
        mock_ast_cache.get_ast.assert_called_once()
        mock_ast_cache.store_ast.assert_called_once()
        
        # Verify result
        assert isinstance(result, ParserResult)
        assert result.ast is not None
        assert "type" in result.ast
        assert result.features == {"features": {"functions": 1}}
    
    async def test_parse_with_error(self, parser, mock_ast_cache):
        """Test parsing when an error occurs."""
        source_code = "def test_function() syntax error"
        mock_ast_cache.get_ast.return_value = None
        
        # Mock _parse_source to raise an exception
        with patch.object(parser, '_parse_source', side_effect=Exception("Parsing failed")):
            result = await parser.parse(source_code)
        
        # Verify cache interaction
        mock_ast_cache.get_ast.assert_called_once()
        mock_ast_cache.store_ast.assert_not_called()  # No AST to store because of error
        
        # Verify result
        assert result is None
    
    def test_cleanup(self, parser):
        """Test cleanup functionality."""
        # Mock feature extractor
        parser.feature_extractor = MagicMock()
        
        parser.cleanup()
        
        # Verify feature extractor was cleaned up
        parser.feature_extractor.cleanup.assert_called_once()
    
    def test_create_node(self, parser):
        """Test the _create_node helper method."""
        node = parser._create_node("function", [1, 0], [5, 10], name="test_function")
        
        assert node["type"] == "function"
        assert node["start_point"] == [1, 0]
        assert node["end_point"] == [5, 10]
        assert node["children"] == []
        assert node["name"] == "test_function"
    
    def test_compile_patterns(self, parser):
        """Test the _compile_patterns helper method."""
        patterns_dict = {
            "code": {
                "function": QueryPattern(
                    name="function",
                    pattern=r"def\s+(\w+)\s*\(",
                    pattern_type=PatternType.CODE
                )
            }
        }
        
        compiled = parser._compile_patterns(patterns_dict)
        
        assert "function" in compiled
        assert hasattr(compiled["function"], "search")  # Verify it's a compiled regex
        
        # Test the compiled regex works
        match = compiled["function"].search("def test_function():")
        assert match is not None
        assert match.group(1) == "test_function"
    
    @pytest.mark.asyncio
    async def test_extract_category_features(self, parser, sample_ast):
        """Test the _extract_category_features method."""
        # Mock feature extractor
        parser.feature_extractor = MagicMock()
        parser.feature_extractor.extract_category.return_value = {
            "count": 1,
            "complexity": 2
        }
        
        features = parser._extract_category_features(
            "functions",
            sample_ast,
            "def test_function():\n    pass"
        )
        
        # Verify feature extractor was called correctly
        parser.feature_extractor.extract_category.assert_called_once_with(
            "functions", 
            sample_ast, 
            "def test_function():\n    pass"
        )
        
        assert features == {"count": 1, "complexity": 2}


if __name__ == "__main__":
    pytest.main() 