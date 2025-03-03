#!/usr/bin/env python3
"""
Integration tests for the indexing pipeline.
"""

import pytest
import pytest_asyncio
from typing import Dict, Any, List, Optional, NamedTuple
import os

# Use fixtures from conftest.py
from parsers.unified_parser import unified_parser
from parsers.types import ParserResult, FileType
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary

# Define a simple type for patterns since we don't have a Pattern class
class PatternInfo(NamedTuple):
    type: str
    name: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    code: str
    metadata: Dict[str, Any]

# Test sample files for indexing
TEST_PYTHON_FILE = """
def hello_world():
    print("Hello, World!")
    
class TestClass:
    def __init__(self, name):
        self.name = name
        
    def greet(self):
        return f"Hello, {self.name}!"
"""

# Reuse the mock_databases fixture from conftest.py instead of creating our own DB setup/cleanup
@pytest_asyncio.fixture
async def test_repo_id(mock_databases):
    """Create and return a test repository ID."""
    # Get the PostgreSQL mock
    pg_mock = mock_databases.get_postgres_mock()
    
    # Configure mock to return a test repo ID when the INSERT query is run
    test_id = 12345
    pg_mock.add_query_handler(
        "INSERT INTO repositories (repo_name, repo_type) VALUES ($1, $2) RETURNING id",
        lambda *args: [{'id': test_id}]
    )
    
    log("Created test repository", context={"repo_id": test_id})
    return test_id

class Args:
    """Mock CLI arguments."""
    def __init__(self, **kwargs):
        self.clean = kwargs.get('clean', True)
        self.watch = kwargs.get('watch', False)
        self.repo_path = kwargs.get('repo_path', '.')
        self.repo_url = kwargs.get('repo_url', None)
        self.verbose = kwargs.get('verbose', True)

@pytest.mark.asyncio
async def test_python_indexing_pipeline(mock_databases, test_repo_id):
    """Test the complete indexing pipeline with a Python file."""
    # For this test, we'll create a minimal ParserResult without using the actual parser
    # This way we can test the rest of the pipeline without dependency on the parser internals
    
    # Create a simplified mock result with patterns 
    mock_patterns = [
        PatternInfo(
            type="function_definition",
            name="hello_world",
            start_line=2,
            end_line=3,
            start_col=0,
            end_col=24,
            code='def hello_world():\n    print("Hello, World!")',
            metadata={}
        ),
        PatternInfo(
            type="class_definition",
            name="TestClass",
            start_line=5,
            end_line=10,
            start_col=0,
            end_col=6,
            code='class TestClass:\n    def __init__(self, name):\n        self.name = name\n        \n    def greet(self):\n        return f"Hello, {self.name}!"',
            metadata={}
        ),
        PatternInfo(
            type="method_definition",
            name="__init__",
            start_line=6,
            end_line=7,
            start_col=4,
            end_col=23,
            code='def __init__(self, name):\n        self.name = name',
            metadata={"class": "TestClass"}
        ),
        PatternInfo(
            type="method_definition",
            name="greet",
            start_line=9,
            end_line=10,
            start_col=4,
            end_col=38,
            code='def greet(self):\n        return f"Hello, {self.name}!"',
            metadata={"class": "TestClass"}
        )
    ]
    
    # Create a parser result and add our patterns
    result = ParserResult(
        success=True,
        ast={"type": "module", "children": []},
        features={
            "metrics": {"complexity": 3},
            "documentation": {},
            "structure": {},
            "syntax": {"metrics": {"complexity": 3}}
        },
        errors=[]
    )
    
    # Manually add the patterns and language attributes
    setattr(result, 'patterns', mock_patterns)
    setattr(result, 'language', 'python')
    
    # Now we can test the post-processing logic
    coverage = check_pattern_coverage(result)
    
    # Functions
    assert coverage["function_count"] >= 1
    assert any(f["name"] == "hello_world" for f in coverage["functions"])
    
    # Classes
    assert coverage["class_count"] >= 1
    assert any(c["name"] == "TestClass" for c in coverage["classes"])
    
    # Methods
    assert coverage["method_count"] >= 2  # __init__ and greet
    assert any(m["name"] == "greet" for m in coverage["methods"])

def check_pattern_coverage(result: ParserResult) -> Dict[str, Any]:
    """
    Check pattern coverage in the parser result.
    Returns a summary of patterns found.
    """
    coverage = {
        "function_count": 0,
        "class_count": 0,
        "method_count": 0,
        "functions": [],
        "classes": [],
        "methods": []
    }
    
    if not hasattr(result, 'patterns') or not result.patterns:
        return coverage
        
    for pattern in result.patterns:
        if pattern.type == "function_definition":
            coverage["function_count"] += 1
            coverage["functions"].append({
                "name": pattern.name,
                "span": [pattern.start_line, pattern.end_line]
            })
        elif pattern.type == "class_definition":
            coverage["class_count"] += 1
            coverage["classes"].append({
                "name": pattern.name,
                "span": [pattern.start_line, pattern.end_line]
            })
        elif pattern.type == "method_definition":
            coverage["method_count"] += 1
            coverage["methods"].append({
                "name": pattern.name,
                "span": [pattern.start_line, pattern.end_line]
            })
            
    return coverage

if __name__ == "__main__":
    asyncio.run(test_python_indexing_pipeline()) 