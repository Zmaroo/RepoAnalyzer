import pytest
from pathlib import Path
from tree_sitter_language_pack import get_language, get_parser
from indexer.parsers.query_patterns import get_query_pattern
from indexer.parsers.tree_sitter_query import TreeSitterQueryHandler
from utils.logger import log

@pytest.fixture
def python_query_handler():
    """Initialize Python tree-sitter query handler"""
    python_lang = get_language('python')
    return TreeSitterQueryHandler(language=python_lang, language_name="python")

@pytest.fixture
def test_python_file():
    """Load a test Python file"""
    test_file = Path(__file__).parent / 'test_parse' / 'data' / 'sample.py'
    with open(test_file, 'r') as f:
        return {
            'content': f.read(),
            'path': str(test_file)
        }

@pytest.mark.asyncio
async def test_python_tree_sitter_parsing(python_query_handler, test_python_file):
    """Test Python parsing using tree-sitter"""
    
    # Get parser from tree-sitter-language-pack
    parser = get_parser('python')
    
    # Parse the file
    tree = parser.parse(bytes(test_python_file['content'], 'utf8'))
    assert tree is not None, "Failed to parse Python file"
    assert not tree.root_node.has_error, "Parse tree contains errors"
    
    # Test function detection
    functions = python_query_handler.find_functions(tree.root_node)
    log(f"Found functions: {[f['name'] for f in functions]}", level="debug")
    assert len(functions) > 0, "No functions detected"
    
    # Test class detection
    classes = python_query_handler.find_classes(tree.root_node)
    log(f"Found classes: {[c['name'] for c in classes]}", level="debug")
    
    # Test import detection
    imports = python_query_handler.find_imports(tree.root_node)
    log(f"Found imports: {[i['module'] for i in imports]}", level="debug")
    
    # Test method detection within classes
    for class_node in classes:
        methods = python_query_handler.find_methods(class_node['node'])
        log(f"Found methods in class {class_node['name']}: {[m['name'] for m in methods]}", level="debug")
        assert len(methods) > 0, f"No methods found in class {class_node['name']}"
    
    # Test docstring detection
    docstrings = python_query_handler.find_docstrings(tree.root_node)
    log(f"Found {len(docstrings)} docstrings", level="debug")
    
    # Verify node properties
    for func in functions:
        assert 'name' in func, f"Function missing name: {func}"
        assert 'node' in func, f"Function missing node: {func}"
        assert 'start_point' in func, f"Function missing start_point: {func}"
        assert 'end_point' in func, f"Function missing end_point: {func}"
    
    return {
        'functions': functions,
        'classes': classes,
        'imports': imports,
        'docstrings': docstrings
    } 