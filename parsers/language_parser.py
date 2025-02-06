"""Language parser module using tree-sitter."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from tree_sitter import Language, Node
from typing import Optional, Dict
from utils.logger import logger

# Cache for parsers to avoid recreating them
_parser_cache: Dict[str, tuple[int, Language, Node]] = {}

def get_parser_for_language(language_name: str) -> Optional[tuple[int, Language, Node]]:
    """Get or create parser components for the given language.
    
    Args:
        language_name: Name of the language to get parser for
        
    Returns:
        Tuple of (binding, language, parser) or None if language not supported
    """
    try:
        # Check cache first
        if language_name in _parser_cache:
            return _parser_cache[language_name]
            
        # Create new parser components
        binding = get_binding(language_name)  # int pointing to C binding
        language = get_language(language_name)  # tree_sitter.Language instance
        parser = get_parser(language_name)  # tree_sitter.Parser instance
        
        parser_tuple = (binding, language, parser)
        _parser_cache[language_name] = parser_tuple
        return parser_tuple
        
    except Exception as e:
        logger.warning(f"Could not get parser for language {language_name}: {e}")
        return None

def parse_code(source_code: str, language_name: str) -> Optional[Node]:
    """Parse source code using tree-sitter.
    
    Args:
        source_code: Source code to parse
        language_name: Programming language of the source code
        
    Returns:
        Root node of the AST or None if parsing failed
    """
    try:
        parser_components = get_parser_for_language(language_name)
        if not parser_components:
            return None
            
        _, _, parser = parser_components
        # Parse the code
        tree = parser.parse(bytes(source_code, "utf8"))
        return tree.root_node
        
    except Exception as e:
        logger.error(f"Error parsing {language_name} code: {e}")
        return None

def get_ast_sexp(node: Node) -> str:
    """Get the s-expression representation of an AST node.
    
    Args:
        node: AST node to convert
        
    Returns:
        S-expression string representation of the AST
    """
    return node.sexp()

def get_ast_json(node: Node) -> dict:
    """Get a JSON-compatible dictionary representation of an AST node.
    
    Args:
        node: AST node to convert
        
    Returns:
        Dictionary representation of the AST
    """
    result = {
        "type": node.type,
        "start_point": node.start_point,
        "end_point": node.end_point,
        "start_byte": node.start_byte,
        "end_byte": node.end_byte
    }
    
    if len(node.children) > 0:
        result["children"] = [get_ast_json(child) for child in node.children]
        
    return result

def is_language_supported(language_name: str) -> bool:
    """Check if a language is supported by tree-sitter.
    
    Args:
        language_name: Name of language to check
        
    Returns:
        True if language is supported, False otherwise
    """
    try:
        get_binding(language_name)
        get_language(language_name)
        get_parser(language_name)
        return True
    except Exception:
        return False