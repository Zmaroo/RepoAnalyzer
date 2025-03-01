#!/usr/bin/env python3
"""
Unit tests for the feature extractor module.
Tests both TreeSitterFeatureExtractor and CustomFeatureExtractor classes with real language examples.
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, Any, List, Optional
import tempfile

# Add the parent directory to the path so we can import the project modules properly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules to be tested
from parsers.feature_extractor import (
    BaseFeatureExtractor,
    TreeSitterFeatureExtractor,
    CustomFeatureExtractor
)
from parsers.types import (
    FileType, 
    ParserType, 
    Documentation, 
    ComplexityMetrics, 
    ExtractedFeatures,
    PatternCategory
)
from parsers.models import QueryResult, FileClassification, PatternMatch
from parsers.pattern_processor import pattern_processor
from parsers.language_mapping import get_language_by_extension
from parsers.language_support import language_registry


# Test data paths
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_parse")
TEST_DATA_SUBDIR = os.path.join(TEST_DATA_DIR, "data")


def get_test_file_path(filename: str) -> str:
    """Get the path to a test file."""
    if os.path.exists(os.path.join(TEST_DATA_DIR, filename)):
        return os.path.join(TEST_DATA_DIR, filename)
    return os.path.join(TEST_DATA_SUBDIR, filename)


def read_test_file(filename: str) -> str:
    """Read a test file's content."""
    filepath = get_test_file_path(filename)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# Sample test files for different languages
TEST_FILES = {
    "python": "sample_types.py",
    "javascript": "app.js",
    "typescript": "types.ts",
    "c": "sample.c",
    "cpp": "sample.cpp",
    "java": "Service.java",
    "go": "server.go",
    "ruby": "sample.rb",
    "rust": "sample.rs"
}


@pytest.fixture
def mock_pattern_processor():
    """Mock the pattern processor."""
    with patch("parsers.feature_extractor.pattern_processor") as mock:
        # Configure the mock to return patterns based on actual languages
        def get_patterns_for_file(classification):
            language_id = classification.language_id
            # Return some basic patterns for each language
            return {
                PatternCategory.SYNTAX.value: {
                    "function": {"pattern": "function", "extract": lambda x: {"name": "test_function"}},
                    "class": {"pattern": "class", "extract": lambda x: {"name": "TestClass"}},
                },
                PatternCategory.DOCUMENTATION.value: {
                    "docstring": {"pattern": "docstring", "extract": None},
                    "comment": {"pattern": "comment", "extract": None},
                }
            }
        
        mock.get_patterns_for_file.side_effect = get_patterns_for_file
        mock.validate_pattern.return_value = True
        yield mock


class TestFeatureExtractorIntegration:
    """Test feature extraction with real-world examples from different languages."""
    
    @pytest.fixture
    def feature_extractors(self, mock_pattern_processor):
        """Create feature extractors for various languages."""
        extractors = {}
        for lang_id, filename in TEST_FILES.items():
            file_ext = os.path.splitext(filename)[1]
            file_type = FileType.CODE
            
            # Create both types of extractors for each language
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.TREE_SITTER
                mock_registry.get_language.return_value = MagicMock()
                tree_sitter_extractor = TreeSitterFeatureExtractor(lang_id, file_type)
                # Mock the language initialization
                tree_sitter_extractor._initialize_parser = Mock()
                tree_sitter_extractor._load_patterns = Mock()
                
                # Mock methods to avoid actual parsing
                tree_sitter_extractor._extract_documentation = Mock(return_value=Documentation())
                tree_sitter_extractor._calculate_metrics = Mock(return_value=ComplexityMetrics())
                
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.CUSTOM
                custom_extractor = CustomFeatureExtractor(lang_id, file_type)
                
                # Mock methods to avoid actual parsing
                custom_extractor._extract_documentation = Mock(return_value=Documentation())
                custom_extractor._calculate_metrics = Mock(return_value=ComplexityMetrics())
            
            extractors[lang_id] = {
                "tree_sitter": tree_sitter_extractor,
                "custom": custom_extractor,
                "source_code": read_test_file(filename) if os.path.exists(get_test_file_path(filename)) else ""
            }
        
        return extractors
    
    @pytest.mark.parametrize("lang_id", TEST_FILES.keys())
    def test_tree_sitter_feature_extraction(self, feature_extractors, lang_id):
        """Test extracting features using tree-sitter for various languages."""
        if lang_id not in feature_extractors:
            pytest.skip(f"No extractor available for {lang_id}")
            
        extractor = feature_extractors[lang_id]["tree_sitter"]
        source_code = feature_extractors[lang_id]["source_code"]
        
        # Create a mock AST
        mock_ast = {"root": MagicMock()}
        
        # Mock the _process_query_result method
        with patch.object(extractor, "_process_query_result") as mock_process:
            mock_process.return_value = {
                "type": "function",
                "name": "test_function",
                "start_point": [0, 0],
                "end_point": [5, 5]
            }
            
            # Test the extraction
            features = extractor.extract_features(mock_ast, source_code)
            
            # Verify basic structure
            assert isinstance(features, ExtractedFeatures)
            assert hasattr(features, 'features')
            assert hasattr(features, 'documentation')
            assert hasattr(features, 'metrics')
    
    @pytest.mark.parametrize("lang_id", TEST_FILES.keys())
    def test_custom_feature_extraction(self, feature_extractors, lang_id):
        """Test extracting features using custom parsers for various languages."""
        if lang_id not in feature_extractors:
            pytest.skip(f"No extractor available for {lang_id}")
            
        extractor = feature_extractors[lang_id]["custom"]
        source_code = feature_extractors[lang_id]["source_code"]
        
        # Create a mock AST with some nodes
        mock_ast = {
            "nodes": [
                {
                    "type": "function",
                    "name": "test_function",
                    "content": "function test_function() { }",
                    "start_line": 1,
                    "end_line": 1
                },
                {
                    "type": "class",
                    "name": "TestClass",
                    "content": "class TestClass { }",
                    "start_line": 3,
                    "end_line": 3
                }
            ]
        }
        
        # Test the extraction
        features = extractor.extract_features(mock_ast, source_code)
        
        # Verify basic structure
        assert isinstance(features, ExtractedFeatures)
        assert hasattr(features, 'features')
        assert hasattr(features, 'documentation')
        assert hasattr(features, 'metrics')


class TestFeatureExtractorWithRealAST:
    """Test feature extraction with real ASTs."""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks for tests."""
        # Mock imports to avoid issues with tree-sitter
        self.parser_mock = patch("parsers.feature_extractor.Parser").start()
        self.language_mock = patch("parsers.feature_extractor.Language").start()
        self.language_registry_mock = patch("parsers.feature_extractor.language_registry").start()
        
        # Configure language registry mock
        self.language_registry_mock.get_parser_type.return_value = ParserType.TREE_SITTER
        self.language_registry_mock.get_language.return_value = MagicMock()
        
        yield
        
        # Clean up patches
        patch.stopall()
    
    def test_process_real_query_result(self):
        """Test processing a realistic query result."""
        # Create a TreeSitterFeatureExtractor
        extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
        
        # Mock the _extract_node_features method
        with patch.object(extractor, "_extract_node_features") as mock_extract:
            mock_extract.return_value = {
                "type": "function_definition",
                "text": "def test_function():",
                "start_byte": 0,
                "end_byte": 20,
                "start_point": [0, 0],
                "end_point": [0, 20],
                "is_named": True
            }
            
            # Create a realistic query result
            mock_node = MagicMock()
            mock_node.type = "function_definition"
            
            query_result = QueryResult(
                pattern_name="test_function_pattern",
                node=mock_node,
                captures={"name": MagicMock()}
            )
            query_result.metadata = {"function_name": "test_function"}
            
            # Process the query result
            result = extractor._process_query_result(query_result)
            
            # Verify the result
            assert "type" in result
            assert result["type"] == "function_definition"
            assert "captures" in result
            assert "function_name" in result
            assert result["function_name"] == "test_function"
    
    def test_extract_node_features(self):
        """Test extracting features from a Tree-sitter node."""
        # Create a TreeSitterFeatureExtractor
        extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
        
        # Create a mock node
        mock_node = MagicMock()
        mock_node.type = "function_definition"
        mock_node.text = b"def test_function():"
        mock_node.start_byte = 0
        mock_node.end_byte = 20
        mock_node.start_point = (0, 0)
        mock_node.end_point = (0, 20)
        mock_node.is_named = True
        mock_node.has_error = False
        mock_node.grammar_name = "python"
        mock_node.child_count = 3
        mock_node.named_child_count = 2
        
        # Extract features
        features = extractor._extract_node_features(mock_node)
        
        # Verify the result
        assert "type" in features
        assert features["type"] == "function_definition"
        assert "text" in features
        assert features["text"] == "def test_function():"
        assert "start_byte" in features
        assert features["start_byte"] == 0
        assert "end_byte" in features
        assert features["end_byte"] == 20
        assert "start_point" in features
        assert features["start_point"] == (0, 0)
        assert "end_point" in features
        assert features["end_point"] == (0, 20)
        assert "is_named" in features
        assert features["is_named"] is True


class TestIntegrationWithTestFiles:
    """Test feature extraction with real test files."""
    
    @pytest.fixture
    def python_sample(self):
        """Get a Python sample from the test files."""
        source_path = get_test_file_path("sample_types.py")
        if os.path.exists(source_path):
            with open(source_path, "r", encoding="utf-8") as f:
                return f.read()
        return """
def test_function():
    '''Test docstring'''
    return "Hello, world!"

# Test comment
class TestClass:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        '''Return a greeting'''
        return f"Hello, {self.name}!"
"""
    
    @pytest.mark.parametrize("parser_type", [ParserType.TREE_SITTER, ParserType.CUSTOM])
    def test_extract_documentation_from_python(self, parser_type, python_sample):
        """Test extracting documentation from a Python file."""
        # Create a feature extractor
        if parser_type == ParserType.TREE_SITTER:
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.TREE_SITTER
                mock_registry.get_language.return_value = MagicMock()
                
                extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
                # Mock initialization
                extractor._initialize_parser = Mock()
                extractor._load_patterns = Mock()
        else:
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.CUSTOM
                extractor = CustomFeatureExtractor("python", FileType.CODE)
        
        # Create mock features with documentation
        mock_features = {
            PatternCategory.DOCUMENTATION.value: {
                "docstring": [
                    {"text": "'''Test docstring'''", "start_line": 2, "end_line": 2},
                    {"text": "'''Return a greeting'''", "start_line": 12, "end_line": 12}
                ],
                "comment": [
                    {"text": "# Test comment", "start_line": 5, "end_line": 5}
                ]
            }
        }
        
        # Extract documentation
        documentation = extractor._extract_documentation(mock_features)
        
        # Verify the result
        assert isinstance(documentation, Documentation)
        assert len(documentation.docstrings) == 2
        assert documentation.docstrings[0]["text"] == "'''Test docstring'''"
        assert len(documentation.comments) == 1
        assert documentation.comments[0]["text"] == "# Test comment"
        assert "'''Test docstring'''" in documentation.content
        assert "'''Return a greeting'''" in documentation.content
    
    @pytest.mark.parametrize("parser_type", [ParserType.TREE_SITTER, ParserType.CUSTOM])
    def test_calculate_metrics_from_python(self, parser_type, python_sample):
        """Test calculating metrics from a Python file."""
        # Create a feature extractor
        if parser_type == ParserType.TREE_SITTER:
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.TREE_SITTER
                mock_registry.get_language.return_value = MagicMock()
                
                extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
                # Mock initialization
                extractor._initialize_parser = Mock()
                extractor._load_patterns = Mock()
        else:
            with patch("parsers.feature_extractor.language_registry") as mock_registry:
                mock_registry.get_parser_type.return_value = ParserType.CUSTOM
                extractor = CustomFeatureExtractor("python", FileType.CODE)
        
        # Create mock features with syntax elements
        mock_features = {
            PatternCategory.SYNTAX.value: {
                "function": [
                    {"name": "test_function", "start_line": 1, "end_line": 3},
                    {"name": "__init__", "start_line": 8, "end_line": 9},
                    {"name": "greet", "start_line": 11, "end_line": 13}
                ],
                "class": [
                    {"name": "TestClass", "start_line": 6, "end_line": 13}
                ],
                "if_statement": [
                    {"start_line": 3, "end_line": 3}
                ]
            }
        }
        
        # Calculate metrics
        metrics = extractor._calculate_metrics(mock_features, python_sample)
        
        # Verify the result
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.cyclomatic > 0  # Cyclomatic complexity should be calculated
        assert len(metrics.lines_of_code) > 0  # Line counts should be calculated


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 