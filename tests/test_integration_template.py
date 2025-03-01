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

# Add the parent directory to the path so we can import the project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the modules you need to test
from indexer.file_processor import FileProcessor
from parsers.file_classification import classify_file
# from db.database import Database  # This module doesn't exist
from utils.health_monitor import global_health_monitor
from utils.logger import log

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
    """Create a temporary directory with sample files for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a sample Python file
        with open(os.path.join(temp_dir, "sample.py"), "w") as f:
            f.write("""
def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
""")

        # Create a sample JavaScript file
        with open(os.path.join(temp_dir, "sample.js"), "w") as f:
            f.write("""
function helloWorld() {
    console.log("Hello, World!");
}

helloWorld();
""")

        yield temp_dir
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)


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


# Example test function that tests the integration between file processing and parsing
def test_file_processing_and_parsing_integration(sample_repo):
    """Test that file processing correctly interacts with parsing."""
    # Setup
    file_processor = FileProcessor()
    parser_factory = classify_file
    
    # Process a file
    python_file = os.path.join(sample_repo, "sample.py")
    process_result = file_processor.process_file(python_file)
    
    # Verify that file processing was successful
    assert process_result.success, f"Failed to process {python_file}"
    
    # Now try to parse the processed file
    parser = parser_factory.get_parser(process_result.file_info)
    parse_result = parser.parse(process_result.file_contents)
    
    # Verify that parsing was successful
    assert parse_result.success, "Failed to parse the processed file"
    assert parse_result.ast is not None, "No AST was generated"
    
    # Verify specific features of the parse result
    functions = [node for node in parse_result.ast if node.type == "function_definition"]
    assert len(functions) > 0, "No functions found in the parsed AST"
    
    # Log success
    log(f"Successfully processed and parsed {python_file}", level="info")


# Example test that involves multiple components
def test_end_to_end_processing(sample_repo, mock_db):
    """Test the entire processing pipeline from indexing to database storage."""
    # Start health monitoring for the test
    with global_health_monitor.component_monitor("integration_test"):
        # Setup
        file_processor = FileProcessor()
        parser_factory = classify_file
        
        # Process all files in the sample repo
        processed_files = []
        for root, _, files in os.walk(sample_repo):
            for file in files:
                file_path = os.path.join(root, file)
                processed_files.append(file_processor.process_file(file_path))
        
        # Verify all files were processed
        assert len(processed_files) > 0, "No files were processed"
        assert all(result.success for result in processed_files), "Not all files were processed successfully"
        
        # Parse all processed files
        parsed_files = []
        for process_result in processed_files:
            parser = parser_factory.get_parser(process_result.file_info)
            parse_result = parser.parse(process_result.file_contents)
            parsed_files.append(parse_result)
        
        # Verify all files were parsed
        assert all(result.success for result in parsed_files), "Not all files were parsed successfully"
        
        # Store results in the database
        for i, parse_result in enumerate(parsed_files):
            file_path = processed_files[i].file_info.file_path
            mock_db.insert(file_path, parse_result)
        
        # Verify database operations were called correctly
        assert mock_db.insert.call_count == len(parsed_files), "Not all parse results were stored in the database"
        
        # Verify health monitoring recorded the activity
        health_status = global_health_monitor.get_component_health("integration_test")
        assert health_status.status != "unhealthy", "Health monitor reported unhealthy status during test"


# You can add more test functions below
# def test_another_integration_scenario():
#     """Description of what this test is verifying."""
#     pass


if __name__ == "__main__":
    # This allows you to run this test file directly
    pytest.main(["-xvs", __file__]) 