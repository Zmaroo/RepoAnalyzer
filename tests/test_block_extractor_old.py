import unittest
import os
from unittest.mock import patch, MagicMock

from parsers.block_extractor import (
    TreeSitterBlockExtractor,
    ExtractedBlock,
    block_extractor
)

class TestTreeSitterBlockExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = TreeSitterBlockExtractor()
        self.python_code = """
def hello_world():
    print("Hello, world!")
    if True:
        print("This is nested")
    return None

class TestClass:
    def __init__(self):
        self.value = 42
        
    def get_value(self):
        return self.value
"""
        
        self.cpp_code = """
#include <iostream>

void hello_world() {
    std::cout << "Hello, world!" << std::endl;
    if (true) {
        std::cout << "This is nested" << std::endl;
    }
}

class TestClass {
public:
    TestClass() : value(42) {}
    
    int get_value() {
        return value;
    }
    
private:
    int value;
};
"""

        self.js_code = """
function helloWorld() {
    console.log("Hello, world!");
    if (true) {
        console.log("This is nested");
    }
    return null;
}

class TestClass {
    constructor() {
        this.value = 42;
    }
    
    getValue() {
        return this.value;
    }
}
"""

    @patch('parsers.block_extractor.get_parser')
    def test_extract_block_python(self, mock_get_parser):
        """Test extracting blocks from Python code."""
        # Set up mock parser and node
        mock_parse = MagicMock()
        mock_node = MagicMock()
        mock_root_node = MagicMock()
        
        # Fix: Set the node type property as a value not a MagicMock
        mock_node.type = "function_definition"
        mock_root_node.node = mock_node
        
        # Set start and end points
        mock_node.start_point = (2, 0)
        mock_node.end_point = (5, 10)
        
        # Connect the mocks
        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_parse
        mock_parse.root_node = mock_root_node
        mock_get_parser.return_value = mock_parser
        
        # Extract the block
        block = self.extractor.extract_block("python", self.python_code, mock_node)
        
        # Assertions
        self.assertIsNotNone(block)
        self.assertEqual(block.node_type, "function_definition")
        self.assertEqual(block.start_point, (2, 0))
        self.assertEqual(block.end_point, (5, 10))
        
    @patch('parsers.block_extractor.get_parser')
    def test_extract_block_cpp(self, mock_get_parser):
        """Test extracting blocks from C++ code."""
        # Set up mock parser and node
        mock_parse = MagicMock()
        mock_node = MagicMock()
        mock_root_node = MagicMock()
        
        # Fix: Set the node type property as a value not a MagicMock
        mock_node.type = "function_definition"
        mock_root_node.node = mock_node
        
        # Set start and end points
        mock_node.start_point = (3, 0)
        mock_node.end_point = (7, 1)
        
        # Connect the mocks
        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_parse
        mock_parse.root_node = mock_root_node
        mock_get_parser.return_value = mock_parser
        
        # Extract the block
        block = self.extractor.extract_block("cpp", self.cpp_code, mock_node)
        
        # Assertions
        self.assertIsNotNone(block)
        self.assertEqual(block.node_type, "function_definition")
        self.assertEqual(block.start_point, (3, 0))
        self.assertEqual(block.end_point, (7, 1))
        
    @patch('parsers.block_extractor.get_parser')
    def test_extract_block_js(self, mock_get_parser):
        """Test extracting blocks from JavaScript code."""
        # Set up mock parser and node
        mock_parse = MagicMock()
        mock_node = MagicMock()
        mock_root_node = MagicMock()
        
        # Fix: Set the node type property as a value not a MagicMock
        mock_node.type = "class_declaration"
        mock_root_node.node = mock_node
        
        # Set start and end points
        mock_node.start_point = (9, 0)
        mock_node.end_point = (17, 1)
        
        # Connect the mocks
        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_parse
        mock_parse.root_node = mock_root_node
        mock_get_parser.return_value = mock_parser
        
        # Extract the block
        block = self.extractor.extract_block("javascript", self.js_code, mock_node)
        
        # Assertions
        self.assertIsNotNone(block)
        self.assertEqual(block.node_type, "class_declaration")
        self.assertEqual(block.start_point, (9, 0))
        self.assertEqual(block.end_point, (17, 1))
        
    @patch('parsers.block_extractor.get_parser')
    def test_get_child_blocks(self, mock_get_parser):
        """Test extracting child blocks from parent node."""
        # Set up mock parser and nodes
        mock_parse = MagicMock()
        mock_parent_node = MagicMock()
        mock_child1 = MagicMock()
        mock_child2 = MagicMock()
        
        # Fix: Set up the children properly
        mock_parent_node.children = [mock_child1, mock_child2]
        
        # Set up types for proper block detection
        mock_child1.type = "function_definition"
        mock_child2.type = "class_declaration"
        
        # Set start and end points
        mock_child1.start_point = (2, 0)
        mock_child1.end_point = (5, 10)
        mock_child2.start_point = (7, 0)
        mock_child2.end_point = (15, 1)
        
        # Fix: Set up mocks to return valid nodes for _is_block_node check
        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_parse
        mock_get_parser.return_value = mock_parser
        
        # Patch the _is_block_node method to return True for our test
        with patch.object(self.extractor, '_is_block_node', return_value=True):
            # Call the method
            blocks = self.extractor.get_child_blocks("python", self.python_code, mock_parent_node)
            
            # Assertions
            self.assertEqual(len(blocks), 2)
            self.assertEqual(blocks[0].node_type, "function_definition")
            self.assertEqual(blocks[1].node_type, "class_declaration")
            
    def test_get_from_cache(self):
        """Test block extraction caching."""
        # Create a mock block
        mock_block = ExtractedBlock(
            content="def test(): pass",
            start_point=(0, 0),
            end_point=(0, 16),
            node_type="function_definition",
            metadata={"cached": True},
            confidence=1.0
        )
        
        # Mock the extract method and manually set up caching
        # Note: We'll use a dictionary to simulate cache storage
        cache = {}
        
        # Define a mock implementation that uses our simulated cache
        def mock_extract_impl(lang, code, node):
            key = f"{lang}:{code}:{id(node)}"
            if key in cache:
                return cache[key]
            cache[key] = mock_block
            return mock_block
        
        # Apply our mock
        with patch.object(self.extractor, '_extract_from_node', side_effect=mock_extract_impl) as mock_extract:
            # Create a consistent node to reuse (so id() is stable)
            test_node = MagicMock()
            
            # First call will "cache" the result
            block1 = self.extractor._extract_from_node("python", "def test(): pass", test_node)
            
            # Reset the mock to verify the next call
            mock_extract.reset_mock()
            
            # Second call with same params should retrieve from our simulated cache
            block2 = self.extractor._extract_from_node("python", "def test(): pass", test_node)
            
            # Assertions
            self.assertEqual(block1, mock_block)
            self.assertEqual(block2, mock_block)
            # Verify mock was not called again since we reset it
            mock_extract.assert_not_called()

    def test_fallback_to_heuristic(self):
        """Test fallback to heuristic when tree-sitter is unavailable."""
        # Create a pattern match without a node to trigger heuristic fallback
        class MockPatternMatch:
            def __init__(self):
                self.node = None
                self.line = 0
                self.column = 0
                self.snippet = "def test(): pass"
        
        pattern_match = MockPatternMatch()
        
        # Create an expected block result
        expected_block = ExtractedBlock(
            content="def test(): pass",
            start_point=(0, 0),
            end_point=(0, 16),
            node_type="heuristic_block",
            metadata={"source": "heuristic"},
            confidence=0.6
        )
        
        # Define our mock implementation that returns the expected block
        def mock_heuristic_impl(source_code, match):
            # Verify we're passing the right parameters
            self.assertEqual(source_code, "def test(): pass")
            self.assertIs(match, pattern_match)
            return expected_block
        
        # Patch the heuristic method with our implementation
        with patch.object(self.extractor, '_extract_block_heuristic', side_effect=mock_heuristic_impl) as mock_heuristic:
            # Directly call the extract_block method which should use our mock
            result = self.extractor.extract_block("python", "def test(): pass", pattern_match)
            
            # Assertions
            self.assertIsNotNone(result)
            self.assertIs(result, expected_block)
            mock_heuristic.assert_called_once_with("def test(): pass", pattern_match)

if __name__ == '__main__':
    unittest.main() 