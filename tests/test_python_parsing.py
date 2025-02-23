"""Test the complete Python parsing pipeline."""

import pytest
from pathlib import Path
from tree_sitter_language_pack import get_language
from parsers.unified_parser import unified_parser
from parsers.models import ParserResult
from parsers.file_classification import FileType, get_file_classification
from parsers.language_support import language_registry
from utils.logger import log

@pytest.fixture
def test_python_file():
    """Load a test Python file"""
    test_file = Path(__file__).parent / 'test_parse' / 'data' / 'inspect_ast.py'
    with open(test_file, 'r') as f:
        return {
            'content': f.read(),
            'path': str(test_file)
        }

@pytest.mark.asyncio
async def test_complete_python_parsing_pipeline(test_python_file):
    """Test the complete Python parsing pipeline from classification to feature extraction"""
    
    file_path = test_python_file['path']
    content = test_python_file['content']
    
    # Test file classification
    classification = get_file_classification(file_path)
    assert classification is not None, "Failed to classify Python file"
    assert classification.file_type == FileType.CODE, "Incorrect file type classification"
    
    # Test language detection and parser availability
    language_info = language_registry.get_language_info(file_path)
    assert language_info.is_supported, "Python should be supported"
    assert language_info.canonical_name == "python", "Failed to detect Python language"
    
    # Verify language is supported by tree-sitter-language-pack
    try:
        get_language(language_info.canonical_name)
    except LookupError:
        pytest.fail("Python not supported by tree-sitter-language-pack")
    
    parser = language_registry.get_parser(language_info)
    assert parser is not None, "Failed to get parser for Python"
    
    # Test unified parsing
    parse_result = await unified_parser.parse_file(file_path, content)
    assert isinstance(parse_result, ParserResult), "Parser did not return ParserResult"
    assert parse_result.success, "Parsing failed"
    
    # Test AST structure
    assert parse_result.ast is not None, "No AST generated"
    assert isinstance(parse_result.ast, dict), "AST should be a dictionary"
    assert parse_result.ast.get("type") == "tree-sitter", "Wrong AST type"
    assert "root" in parse_result.ast, "Missing root node in AST"
    
    # Test extracted features
    features = parse_result.features
    assert features is not None, "No features extracted"
    
    # Test structural features
    assert 'structure' in features, "Missing structure features"
    assert 'functions' in features['structure'], "Missing functions in structure"
    assert len(features['structure']['functions']) > 0, "No functions detected"
    
    # Test syntax features
    assert 'syntax' in features, "Missing syntax features"
    assert 'identifiers' in features['syntax'], "Missing identifiers in syntax"
    
    # Test metrics
    assert 'metrics' in features, "Missing metrics"
    metrics = features['metrics']
    assert metrics['cyclomatic'] >= 0, "Invalid cyclomatic complexity"
    assert metrics['cognitive'] >= 0, "Invalid cognitive complexity"
    assert isinstance(metrics['halstead'], dict), "Missing Halstead metrics"
    assert metrics['maintainability_index'] >= 0, "Invalid maintainability index"
    assert metrics['node_count'] >= 0, "Invalid node count"
    
    # Test function detection via structure
    assert len(features['structure']['functions']) == 2, "Expected 2 functions"
    
    # Test function count from structure
    assert 'function_count' in features, "Missing function count"
    assert features['function_count'] >= 0, "Invalid function count"
    assert 'functions' in features['structure'], "Missing function details"
    
    # Test class detection
    assert 'class_count' in features, "Missing class count"
    assert 'classes' in features['structure'], "Missing class details"
    
    # Test method detection
    for class_info in features['structure']['classes']:
        assert 'methods' in class_info, f"Missing methods in class {class_info.get('name')}"
    
    # Test import detection
    assert 'import_count' in features, "Missing import count"
    assert 'imports' in features['semantics'], "Missing import details"
    
    # Test documentation
    assert 'documentation' in features, "Missing documentation"
    assert isinstance(features['documentation']['comments'], list), "Missing comments"
    
    # Test complexity metrics
    complexity = parse_result.complexity
    assert complexity is not None, "No complexity metrics"
    assert 'cyclomatic' in complexity, "Missing cyclomatic complexity"
    assert complexity['cyclomatic'] >= 1, "Invalid cyclomatic complexity"
    
    # Test statistics
    stats = parse_result.statistics
    assert stats is not None, "No parsing statistics generated"
    assert stats['parse_time_ms'] > 0, "Invalid parsing time"
    assert stats['total_nodes_processed'] > 0, "No nodes processed"

    return parse_result 