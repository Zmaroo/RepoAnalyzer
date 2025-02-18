"""Language parser module using tree-sitter with custom logger callback."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from tree_sitter import Language, Node, LogType
from typing import Optional, Dict, Tuple
from utils.logger import log
import os
import threading
from parsers.language_mapping import (
    normalize_language_name, 
    LanguageSupport,
    CUSTOM_PARSER_FUNCTIONS,
    get_file_classification
)
from parsers.common_parser_utils import build_parser_output
from file_parser import get_root_node
from query_patterns import get_query_patterns
from ast_extractor import extract_ast_features

# Set this to False to disable the custom logger callback (helpful when debugging seg faults).
ATTACH_LOGGER_CALLBACK = True

# Cache for parsers to avoid recreating them.
_parser_cache: Dict[str, Tuple[int, Language, object]] = {}
# Locks to serialize access to each cached parser (since Tree‑sitter parser instances are not thread‑safe).
_parser_locks: Dict[str, threading.Lock] = {}

def tree_sitter_logger(log_type: int, message: str) -> None:
    """Custom logger callback for the Tree-sitter parser."""
    # Skip logging of skipped characters to reduce noise
    if "skip character" in message:
        return
        
    if log_type == LogType.LEX:
        # Only log important lexer events
        if any(key in message for key in ["accept", "error", "invalid"]):
            log(f"Tree-sitter [LEX]: {message}", level="debug")
    elif log_type == LogType.PARSE:
        # Log all parse events except internal state changes
        if not message.startswith("lex_internal"):
            log(f"Tree-sitter [PARSE]: {message}", level="debug")
    else:
        log(f"Tree-sitter [UNKNOWN-{log_type}]: {message}", level="debug")

def get_parser_for_language(language_name: str) -> Optional[Tuple[int, Language, object]]:
    """
    Get or create parser components for the given language.
    
    Args:
        language_name: Name of the language to get parser for.
        
    Returns:
        Tuple of (binding, language, parser) or None if the language is not supported.
    """
    try:
        if language_name not in _parser_locks:
            _parser_locks[language_name] = threading.Lock()

        if language_name in _parser_cache:
            log(f"Using cached parser for {language_name}", level="debug")
            return _parser_cache[language_name]
        
        log(f"Creating new parser for {language_name}", level="debug")
        
        try:
            binding = get_binding(language_name)
            log(f"Got binding for {language_name}: {binding}", level="debug")
        except Exception as e:
            log(f"Failed to get binding for {language_name}: {e}", level="error")
            return None

        try:
            language = get_language(language_name)
            log(f"Got language for {language_name}: {language}", level="debug")
        except Exception as e:
            log(f"Failed to get language for {language_name}: {e}", level="error")
            return None

        try:
            parser = get_parser(language_name)
            log(f"Got parser for {language_name}: {parser}", level="debug")
        except Exception as e:
            log(f"Failed to get parser for {language_name}: {e}", level="error")
            return None

        if ATTACH_LOGGER_CALLBACK:
            try:
                parser.logger = tree_sitter_logger
                log("Attached tree-sitter logger callback", level="debug")
            except Exception as e:
                log(f"Failed to attach logger to parser for {language_name}: {e}", level="warning")

        parser_tuple = (binding, language, parser)
        _parser_cache[language_name] = parser_tuple
        return parser_tuple
        
    except Exception as e:
        log(f"Could not get parser for language {language_name}: {e}", level="error")
        return None

def parse_code(source_code: str, file_path: str) -> dict:
    """Parse code using tree-sitter or custom parser."""
    classification = get_file_classification(file_path)
    if not classification:
        return build_parser_output(
            source_code=source_code,
            language="unknown",
            ast={"type": "unparsed"},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        )
    
    # Use custom parser if available
    if classification.parser in CUSTOM_PARSER_FUNCTIONS:
        return CUSTOM_PARSER_FUNCTIONS[classification.parser](source_code)
    
    # Use tree-sitter parser
    parser_components = get_parser_for_language(classification.language)
    if not parser_components:
        return build_parser_output(
            source_code=source_code,
            language=classification.language,
            ast={"type": "unparsed"},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        )
    
    # Parse with tree-sitter
    binding, language, parser = parser_components
    
    # Set custom logger callback if enabled
    if ATTACH_LOGGER_CALLBACK:
        parser.logger = tree_sitter_logger
        
    tree = parser.parse(source_code.encode('utf-8'))
    root = get_root_node(tree)
    
    # Extract features using language-specific query patterns
    query_patterns = get_query_patterns(classification.language)
    features = extract_ast_features(root, language, query_patterns, source_code.encode('utf-8'))
    
    from file_parser import calculate_complexity
    
    return build_parser_output(
        source_code=source_code,
        language=classification.language,
        ast=get_ast_json(root),
        features=features,
        total_lines=len(source_code.splitlines()),
        documentation=features.get("documentation", {}).get("docstring", ""),
        complexity=calculate_complexity(root)
    )

def get_ast_json(node: Node) -> dict:
    """
    Get a JSON-compatible dictionary representation of an AST node.
    
    Args:
        node: AST node to convert.
        
    Returns:
        Dictionary representation of the AST.
    """
    result = {
        "type": node.type,
        "start_point": node.start_point,
        "end_point": node.end_point,
        "start_byte": node.start_byte,
        "end_byte": node.end_byte
    }
    
    if node.children:
        result["children"] = [get_ast_json(child) for child in node.children]
        
    return result