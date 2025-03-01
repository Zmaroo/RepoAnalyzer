#!/usr/bin/env python3
"""
Integration test for the indexer module after fixing circular dependencies.
"""

import os
import asyncio
from indexer import FileProcessor, get_file_classification
from parsers.file_classification import classify_file
from indexer.common import async_read_file
from parsers.pattern_processor import pattern_processor

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('parsers.pattern_processor').setLevel(logging.DEBUG)
logging.getLogger('parsers.file_classification').setLevel(logging.DEBUG)
logging.getLogger('indexer').setLevel(logging.DEBUG)

async def test_file_classification():
    """Test file classification from both modules."""
    test_files = [
        'parsers/file_classification.py',  # Python file
        'indexer/common.py',               # Our new module
        'indexer/__init__.py',             # Package init file
        'pjt_notes/improvement_roadmap.md', # Markdown
    ]
    
    print("\n=== Testing File Classification ===")
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"Skipping {file_path} - file does not exist")
            continue
        
        # Test both classification methods
        direct_classification = classify_file(file_path)
        indexer_classification = get_file_classification(file_path)
        
        print(f"File: {file_path}")
        print(f"  Direct Language: {direct_classification.language_id}")
        print(f"  Indexer Language: {indexer_classification.language_id}")
        print(f"  Parser Type: {direct_classification.parser_type}")

async def test_async_read_file():
    """Test the async_read_file function from the common module."""
    test_file = 'pjt_notes/improvement_roadmap.md'
    
    print("\n=== Testing Async File Reading ===")
    if not os.path.exists(test_file):
        print(f"Skipping - {test_file} does not exist")
        return
    
    content = await async_read_file(test_file)
    if content:
        print(f"Successfully read {test_file}")
        print(f"  Content length: {len(content)} characters")
        print(f"  First line: {content.split('\n')[0]}")
    else:
        print(f"Failed to read {test_file}")

async def test_file_processor():
    """Test the FileProcessor initialization."""
    print("\n=== Testing FileProcessor ===")
    processor = FileProcessor()
    print("FileProcessor instantiated successfully")
    print(f"  Pattern processor: {processor._pattern_processor.__class__.__name__}")
    print(f"  Language registry: {processor._language_registry.__class__.__name__ if processor._language_registry else 'None'}")
    print(f"  Semaphore value: {processor._semaphore._value}")

async def main():
    """Run all tests."""
    print("Starting integration tests for the indexer module...")
    
    await test_file_classification()
    await test_async_read_file()
    await test_file_processor()
    
    print("\nIntegration tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 