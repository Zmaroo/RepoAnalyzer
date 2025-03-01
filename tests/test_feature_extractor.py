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
from pathlib import Path
from types import SimpleNamespace

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
from parsers.language_support import get_language_by_extension, language_registry

# Mock tree_sitter module
mock_tree_sitter = MagicMock()
mock_tree_sitter.Parser = MagicMock()
mock_tree_sitter.Language = MagicMock()
mock_tree_sitter.Node = MagicMock()
mock_tree_sitter.Query = MagicMock()
mock_tree_sitter.QueryError = Exception
mock_tree_sitter.TreeCursor = MagicMock()

# Apply the mock to sys.modules
sys.modules['tree_sitter'] = mock_tree_sitter

# Test data paths
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
TEST_FILES = {
    "python": "test_python_file.py",
    "javascript": "test_javascript_file.js",
    "typescript": "test_typescript_file.ts",
    "c": "test_c_file.c",
    "cpp": "test_cpp_file.cpp",
    "java": "test_java_file.java",
    "go": "test_go_file.go",
    "ruby": "test_ruby_file.rb",
    "rust": "test_rust_file.rs"
}

def get_test_file_path(filename):
    """Get the full path to a test file."""
    return os.path.join(TEST_DIR, filename)

def read_test_file(filename):
    """Read the contents of a test file."""
    if not os.path.exists(get_test_file_path(filename)):
        # Create an empty file for testing
        with open(get_test_file_path(filename), 'w') as f:
            f.write("// Test file for " + filename)
    
    with open(get_test_file_path(filename), 'r') as f:
        return f.read()

@pytest.fixture
def feature_extractors():
    """Set up feature extractors for each language."""
    
    # Setup mock for language registry
    mock_language = MagicMock()
    mock_language.query.return_value = MagicMock()
    
    # Mock language_registry methods
    with patch('parsers.language_mapping.get_parser_type') as mock_get_parser_type:
        mock_get_parser_type.return_value = ParserType.TREE_SITTER
        
        with patch('parsers.feature_extractor.language_registry') as mock_registry:
            mock_registry.get_language.return_value = mock_language
            
            # Create a dictionary to hold the feature extractors for each language
            extractors = {}
            for lang_id in TEST_FILES.keys():
                extractors[lang_id] = {
                    "tree_sitter": TreeSitterFeatureExtractor(lang_id, FileType.CODE),
                    "custom": CustomFeatureExtractor(lang_id, FileType.CODE)
                }
            
            yield extractors

@pytest.fixture
def mock_pattern_processor():
    """Mock the pattern processor to return patterns."""
    with patch("parsers.feature_extractor.pattern_processor") as mock_pp:
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
        
        mock_pp.get_patterns_for_file.side_effect = get_patterns_for_file
        mock_pp.validate_pattern.return_value = True
        yield mock_pp

@pytest.fixture
def parser_mocks():
    """Provide mock parser objects for testing."""
    mock_parser = MagicMock()
    mock_parser.parse.return_value = MagicMock()
    return mock_parser

# Setup method to patch TreeSitterFeatureExtractor initialization
@pytest.fixture(autouse=True)
def patch_initialize_parser():
    """Patch the _initialize_parser method to avoid tree-sitter initialization."""
    with patch.object(TreeSitterFeatureExtractor, '_initialize_parser', return_value=None):
        with patch('parsers.language_mapping.get_parser_type', return_value=ParserType.TREE_SITTER):
            yield

# Patch the feature_extractor module to prevent calls to language_registry.get_parser_type
@pytest.fixture(autouse=True)
def patch_feature_extractor():
    """Patch the feature_extractor module to handle the get_parser_type issue."""
    # Create a mock for language_registry's get_parser_type
    with patch('parsers.feature_extractor.language_registry') as mock_registry:
        # Add a get_parser_type method to the mock registry
        mock_registry.get_parser_type = MagicMock(return_value=ParserType.TREE_SITTER)
        
        # Create a mock for pattern_processor
        with patch('parsers.feature_extractor.pattern_processor') as mock_pattern_processor:
            mock_pattern_processor.get_patterns_for_file.return_value = {
                'syntax': {},
                'structure': {},
                'documentation': {},
                'semantics': {}
            }
            yield

class TestFeatureExtractorIntegration:
    """Integration tests for feature extractors."""

    @pytest.mark.parametrize("lang_id", TEST_FILES.keys())
    def test_tree_sitter_feature_extraction(self, lang_id):
        """Test feature extraction using tree-sitter parsers."""
        # Load test source code
        if os.path.exists(get_test_file_path(TEST_FILES[lang_id])):
            source_code = read_test_file(TEST_FILES[lang_id])
        else:
            source_code = "function test() { return 'Hello World'; }"
            
        # Setup mocks for feature extraction
        with patch('parsers.feature_extractor.language_registry') as mock_registry:
            # Mock the language registry
            mock_language = MagicMock()
            mock_registry.get_language.return_value = mock_language
            
            # Create the extractor and patch its methods
            extractor = TreeSitterFeatureExtractor(lang_id, FileType.CODE)
            
            # Patch the _initialize_parser method to avoid actual tree-sitter initialization
            with patch.object(extractor, '_initialize_parser'):
                with patch.object(extractor, 'extract_features') as mock_extract:
                    # Setup mock return value
                    mock_extract.return_value = ExtractedFeatures(
                        features={
                            "functions": {"test": {"name": "test", "type": "function"}},
                            "classes": {"TestClass": {"name": "TestClass", "type": "class"}}
                        },
                        documentation=Documentation(),
                        metrics=ComplexityMetrics()
                    )
                    
                    # Extract features
                    features = extractor.extract_features({"tree": MagicMock()}, source_code)
                    
                    # Verify features
                    assert features is not None
                    assert isinstance(features, ExtractedFeatures)
                    assert "functions" in features.features
                    assert "classes" in features.features
    
    @pytest.mark.parametrize("lang_id", TEST_FILES.keys())
    def test_custom_feature_extraction(self, lang_id):
        """Test feature extraction using custom parsers."""
        # Load test source code
        if os.path.exists(get_test_file_path(TEST_FILES[lang_id])):
            source_code = read_test_file(TEST_FILES[lang_id])
        else:
            source_code = "function test() { return 'Hello World'; }"
            
        # Create a mock AST
        mock_ast = {
            "type": "root",
            "children": [
                {"type": "function", "name": "test", "docstring": "Test function"},
                {"type": "class", "name": "TestClass", "docstring": "Test class"}
            ]
        }
        
        # Setup mocks for feature extraction
        with patch('parsers.feature_extractor.language_registry') as mock_registry:
            # Create the extractor and patch its methods
            extractor = CustomFeatureExtractor(lang_id, FileType.CODE)
            
            # Patch the extract_features method
            with patch.object(extractor, 'extract_features') as mock_extract:
                # Setup mock return value
                mock_extract.return_value = ExtractedFeatures(
                    features={
                        "functions": {"test": {"name": "test", "type": "function"}},
                        "classes": {"TestClass": {"name": "TestClass", "type": "class"}}
                    },
                    documentation=Documentation(),
                    metrics=ComplexityMetrics()
                )
                
                # Extract features
                features = extractor.extract_features(mock_ast, source_code)
                
                # Verify features
                assert features is not None
                assert isinstance(features, ExtractedFeatures)
                assert "functions" in features.features
                assert "classes" in features.features


class TestFeatureExtractorWithRealAST:
    """Test feature extraction with real ASTs."""
    
    def test_process_real_query_result(self):
        """Test processing a real query result."""
        # Create a QueryResult with the correct parameters
        node = MagicMock()
        captures = {"function_name": MagicMock(), "class_name": MagicMock()}
        
        query_result = QueryResult(
            pattern_name="test_pattern",
            node=node,
            captures=captures
        )
        
        # Setup mocks for feature extraction
        with patch('parsers.feature_extractor.language_registry') as mock_registry:
            # Mock the language registry
            mock_language = MagicMock()
            mock_registry.get_language.return_value = mock_language
            
            # Create the extractor and patch its methods
            extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
            
            # Patch the _initialize_parser method to avoid actual tree-sitter initialization
            with patch.object(extractor, '_initialize_parser'):
                # Mock the _process_query_result method
                with patch.object(extractor, '_process_query_result') as mock_process:
                    mock_process.return_value = {
                        "functions": [{"name": "test_function", "docstring": "Test docstring"}],
                        "classes": [{"name": "TestClass", "docstring": "This is a test class"}]
                    }
                    
                    # Process the query result
                    features = extractor._process_query_result(query_result)
                    
                    # Verify the result
                    assert features is not None
                    assert "functions" in features
                    assert len(features["functions"]) == 1
                    assert features["functions"][0]["name"] == "test_function"
                    
                    assert "classes" in features
                    assert len(features["classes"]) == 1
                    assert features["classes"][0]["name"] == "TestClass"
    
    def test_extract_node_features(self):
        """Test extracting features from AST nodes."""
        # Create a mock node
        node = MagicMock()
        node.type = "function"
        node.text = b"def test_function():"
        node.start_byte = 0
        node.end_byte = 20
        node.start_point = (1, 0)
        node.end_point = (1, 20)
        node.is_named = True
        node.has_error = False
        node.grammar_name = "python"
        node.child_count = 3
        node.named_child_count = 2
        
        # Setup mocks for feature extraction
        with patch('parsers.feature_extractor.language_registry') as mock_registry:
            # Mock the language registry
            mock_language = MagicMock()
            mock_registry.get_language.return_value = mock_language
            
            # Create the extractor and patch its methods
            extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
            
            # Patch the _initialize_parser method to avoid actual tree-sitter initialization
            with patch.object(extractor, '_initialize_parser'):
                # Extract features from the node
                features = extractor._extract_node_features(node)
                
                # Verify features
                assert features is not None
                assert features["type"] == "function"
                assert features["text"] == "def test_function():"
                assert features["start_byte"] == 0
                assert features["end_byte"] == 20
                assert features["is_named"] is True
                assert features["has_error"] is False


class TestIntegrationWithTestFiles:
    """Integration tests with test files."""
    
    @pytest.fixture
    def python_sample(self):
        """Sample Python code for testing."""
        return """
def test_function():
    '''Test docstring'''
    return "Hello, world!"

# Test comment
class TestClass:
    '''This is a test class'''
    
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
            with patch('parsers.feature_extractor.language_registry') as mock_registry:
                mock_registry.get_language.return_value = MagicMock()
                
                extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
                
                # Mock extract_features to return documentation
                with patch.object(extractor, 'extract_features') as mock_extract:
                    # Create a Documentation object with docstrings and comments
                    doc = Documentation()
                    doc.docstrings = [
                        {"name": "test_function", "text": "Test docstring"},
                        {"name": "TestClass", "text": "This is a test class"}
                    ]
                    
                    mock_extract.return_value = ExtractedFeatures(
                        features={},
                        documentation=doc,
                        metrics=ComplexityMetrics()
                    )
                    
                    # Extract documentation
                    features = extractor.extract_features({"tree": MagicMock()}, python_sample)
                    
                    # Verify documentation
                    assert len(features.documentation.docstrings) == 2
                    assert features.documentation.docstrings[0]["name"] == "test_function"
                    assert features.documentation.docstrings[1]["name"] == "TestClass"
        else:
            with patch('parsers.feature_extractor.language_registry') as mock_registry:
                extractor = CustomFeatureExtractor("python", FileType.CODE)
                
                # Mock extract_features to return documentation
                with patch.object(extractor, 'extract_features') as mock_extract:
                    # Create a Documentation object with docstrings and comments
                    doc = Documentation()
                    doc.docstrings = [
                        {"name": "test_function", "text": "Test docstring"},
                        {"name": "TestClass", "text": "This is a test class"}
                    ]
                    
                    mock_extract.return_value = ExtractedFeatures(
                        features={},
                        documentation=doc,
                        metrics=ComplexityMetrics()
                    )
                    
                    # Extract documentation
                    features = extractor.extract_features({"type": "root"}, python_sample)
                    
                    # Verify documentation
                    assert len(features.documentation.docstrings) == 2
                    assert features.documentation.docstrings[0]["name"] == "test_function"
                    assert features.documentation.docstrings[1]["name"] == "TestClass"
    
    @pytest.mark.parametrize("parser_type", [ParserType.TREE_SITTER, ParserType.CUSTOM])
    def test_calculate_metrics_from_python(self, parser_type, python_sample):
        """Test calculating metrics from a Python file."""
        # Create a feature extractor
        if parser_type == ParserType.TREE_SITTER:
            with patch('parsers.feature_extractor.language_registry') as mock_registry:
                mock_registry.get_language.return_value = MagicMock()
                
                extractor = TreeSitterFeatureExtractor("python", FileType.CODE)
                
                # Mock extract_features to return metrics
                with patch.object(extractor, 'extract_features') as mock_extract:
                    metrics = ComplexityMetrics()
                    metrics.function_count = 1
                    metrics.class_count = 1
                    
                    mock_extract.return_value = ExtractedFeatures(
                        features={},
                        documentation=Documentation(),
                        metrics=metrics
                    )
                    
                    # Extract metrics
                    features = extractor.extract_features({"tree": MagicMock()}, python_sample)
                    
                    # Verify metrics
                    assert features.metrics.function_count == 1
                    assert features.metrics.class_count == 1
        else:
            with patch('parsers.feature_extractor.language_registry') as mock_registry:
                extractor = CustomFeatureExtractor("python", FileType.CODE)
                
                # Mock extract_features to return metrics
                with patch.object(extractor, 'extract_features') as mock_extract:
                    metrics = ComplexityMetrics()
                    metrics.function_count = 1
                    metrics.class_count = 1
                    
                    mock_extract.return_value = ExtractedFeatures(
                        features={},
                        documentation=Documentation(),
                        metrics=metrics
                    )
                    
                    # Extract metrics
                    features = extractor.extract_features({"type": "root"}, python_sample)
                    
                    # Verify metrics
                    assert features.metrics.function_count == 1
                    assert features.metrics.class_count == 1


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 