#!/usr/bin/env python3
"""
Direct test script for the parsers module.
This avoids the circular imports in the indexer module.
"""

import os
import asyncio
from parsers.file_classification import classify_file
from parsers.pattern_processor import pattern_processor
from parsers.types import ParserType

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('parsers.pattern_processor').setLevel(logging.DEBUG)
logging.getLogger('parsers.file_classification').setLevel(logging.DEBUG)

async def test_file_classification():
    """Test file classification on various file types."""
    test_files = [
        'parsers/file_classification.py',  # Python file
        'parsers/query_patterns/__init__.py',  # Python package
        'README.md' if os.path.exists('README.md') else 'pjt_notes/improvement_roadmap.md',  # Markdown
        'parsers/query_patterns/dockerfil.py'  # Custom parser
    ]
    
    print("\n=== Testing File Classification ===")
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"Skipping {file_path} - file does not exist")
            continue
            
        classification = classify_file(file_path)
        print(f"File: {file_path}")
        print(f"  Language: {classification.language_id}")
        print(f"  Parser Type: {classification.parser_type}")
        print(f"  Is Binary: {classification.is_binary}")

async def test_pattern_loading():
    """Test pattern loading for various languages."""
    test_languages = ['python', 'javascript', 'dockerfile', 'markdown']
    
    print("\n=== Testing Pattern Loading ===")
    for language in test_languages:
        from parsers.models import FileClassification
        from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES
        
        # Create a mock classification
        parser_type = ParserType.TREE_SITTER if language in TREE_SITTER_LANGUAGES else ParserType.CUSTOM
        classification = FileClassification(
            file_path=f"test.{language}",
            language_id=language,
            parser_type=parser_type
        )
        
        # Try to get patterns
        patterns = pattern_processor.get_patterns_for_file(classification)
        print(f"Language: {language}")
        print(f"  Parser Type: {parser_type}")
        print(f"  Patterns found: {len(patterns)}")
        if patterns:
            print(f"  Pattern examples: {list(patterns.keys())[:3]}")

async def main():
    """Run all tests."""
    print("Starting parser tests...")
    
    await test_file_classification()
    await test_pattern_loading()
    
    print("\nParser tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 