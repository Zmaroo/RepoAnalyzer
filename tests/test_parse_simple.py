#!/usr/bin/env python3
"""
Simple test script for RepoAnalyzer parsers.

This script tests the parsers on the files in the test_parse directory,
avoiding the use of any decorated async functions that might cause issues.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the core parsing components
from parsers.file_classification import classify_file
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES
from parsers.types import ParserType
from utils.logger import log

# Path to the test_parse directory
TEST_PARSE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests', 'test_parse')

def test_file_classification():
    """Test file classification on the test_parse directory files."""
    print("\n=== Testing File Classification ===")
    
    # Check if test_parse directory exists
    if not os.path.exists(TEST_PARSE_DIR):
        print(f"Error: Test directory not found: {TEST_PARSE_DIR}")
        return False
    
    # Get list of files to test
    files = []
    for root, _, filenames in os.walk(TEST_PARSE_DIR):
        for filename in filenames:
            # Skip hidden files
            if not filename.startswith('.'):
                files.append(os.path.join(root, filename))
    
    if not files:
        print("No files found in test directory.")
        return False
    
    # Test classification for each file
    for file_path in files:
        print(f"\nAnalyzing file: {os.path.relpath(file_path, os.path.dirname(TEST_PARSE_DIR))}")
        
        try:
            # Classify the file
            classification = classify_file(file_path)
            
            print(f"  Language: {classification.language_id}")
            print(f"  Parser Type: {classification.parser_type}")
            print(f"  Is Binary: {classification.is_binary}")
            
            # Get additional information based on language
            if classification.language_id in TREE_SITTER_LANGUAGES:
                print(f"  Tree-Sitter Grammar: Available")
            elif classification.language_id in CUSTOM_PARSER_LANGUAGES:
                print(f"  Custom Parser: Available")
            else:
                print(f"  Parser Support: Limited")
            
        except Exception as e:
            print(f"  Error classifying file: {e}")
    
    print("\nFile classification testing completed.")
    return True

def test_pattern_loading():
    """Test pattern loading for various languages."""
    print("\n=== Testing Pattern Loading ===")
    
    # Test languages to check pattern loading
    test_languages = ['python', 'javascript', 'c', 'cpp']
    
    for language in test_languages:
        print(f"\nTesting pattern loading for: {language}")
        
        try:
            # Try to directly import the language-specific pattern module
            if language == 'python':
                from parsers.query_patterns.python import PYTHON_PATTERNS
                patterns = PYTHON_PATTERNS
            elif language == 'javascript':
                from parsers.query_patterns.javascript import JAVASCRIPT_PATTERNS
                patterns = JAVASCRIPT_PATTERNS
            elif language == 'c':
                from parsers.query_patterns.c import C_PATTERNS
                patterns = C_PATTERNS
            elif language == 'cpp':
                from parsers.query_patterns.cpp import CPP_PATTERNS
                patterns = CPP_PATTERNS
            else:
                patterns = {}
            
            if patterns:
                print(f"  Total patterns: {len(patterns)}")
                print(f"  Pattern examples: {list(patterns.keys())[:3]}")
            else:
                print(f"  No patterns found for {language}")
                
        except ImportError as e:
            print(f"  Error importing patterns module: {e}")
        except AttributeError as e:
            print(f"  Error accessing pattern variable: {e}")
        except Exception as e:
            print(f"  Error loading patterns: {e}")
    
    print("\nPattern loading testing completed.")
    return True

def main():
    """Main entry point for testing."""
    print("Starting RepoAnalyzer parser tests...")
    
    # Test file classification
    test_file_classification()
    
    # Test pattern loading
    test_pattern_loading()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main() 