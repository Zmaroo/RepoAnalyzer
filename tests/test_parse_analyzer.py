#!/usr/bin/env python3
"""
Test for analyzing the test_parse directory.

This test uses the FileProcessor to analyze files in the test_parse directory,
demonstrating how the system parses different file types.
"""

import os
import sys
import pytest
from pathlib import Path

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indexer.file_processor import FileProcessor
from parsers.file_classification import classify_file
from utils.logger import log

# Path to the test_parse directory
TEST_PARSE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'test_parse')

def test_parse_directory():
    """Test parsing all files in the test_parse directory."""
    assert os.path.exists(TEST_PARSE_DIR), f"Test directory not found: {TEST_PARSE_DIR}"
    
    # Initialize file processor
    processor = FileProcessor()
    
    # Process each file
    results = []
    for root, _, files in os.walk(TEST_PARSE_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Skip hidden files and directories
            if os.path.basename(file_path).startswith('.'):
                continue
                
            log(f"Processing file: {file_path}", level="info")
            
            # Classify the file
            classification = classify_file(file_path)
            log(f"  Classification: {classification.language_id} ({classification.parser_type})", level="info")
            
            # Process the file
            result = processor.process_file(file_path)
            
            # Log results
            if result.success:
                log(f"  Successfully processed {file_path}", level="info")
                if hasattr(result, 'ast') and result.ast:
                    log(f"  AST nodes: {len(result.ast)}", level="info")
            else:
                log(f"  Failed to process {file_path}: {result.error_message}", level="warning")
                
            results.append((file_path, result.success))
    
    # Verify at least some files were processed successfully
    successful = [r for r in results if r[1]]
    assert len(successful) > 0, "No files were successfully processed"
    
    # Log summary
    log(f"Processed {len(results)} files, {len(successful)} successfully", level="info")
    
    # Return for inspection
    return results

def test_parse_specific_files():
    """Test parsing specific file types in the test_parse directory."""
    assert os.path.exists(TEST_PARSE_DIR), f"Test directory not found: {TEST_PARSE_DIR}"
    
    # Files to test
    test_files = [
        os.path.join(TEST_PARSE_DIR, 'app.js'),
        os.path.join(TEST_PARSE_DIR, 'sample.c'),
        os.path.join(TEST_PARSE_DIR, 'sample.cpp')
    ]
    
    # Initialize file processor
    processor = FileProcessor()
    
    # Process each file
    for file_path in test_files:
        if not os.path.exists(file_path):
            log(f"File not found: {file_path}", level="warning")
            continue
            
        log(f"Processing file: {file_path}", level="info")
        
        # Classify the file
        classification = classify_file(file_path)
        log(f"  Classification: {classification.language_id} ({classification.parser_type})", level="info")
        
        # Process the file
        result = processor.process_file(file_path)
        
        # Log results
        if result.success:
            log(f"  Successfully processed {file_path}", level="info")
            if hasattr(result, 'ast') and result.ast:
                log(f"  AST nodes: {len(result.ast)}", level="info")
        else:
            log(f"  Failed to process {file_path}: {result.error_message}", level="warning")
        
        # Assertions for specific file types
        assert result.success, f"Failed to process {file_path}"

if __name__ == "__main__":
    # Run the tests
    test_parse_directory()
    test_parse_specific_files() 