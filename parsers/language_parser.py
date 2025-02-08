"""Language parser module using tree-sitter with custom logger callback."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from tree_sitter import Language, Node, LogType
from typing import Optional, Dict, Tuple
from utils.logger import log  # Use the common logger
import os
import threading

# Set this to False to disable the custom logger callback (helpful when debugging seg faults).
ATTACH_LOGGER_CALLBACK = False

# Cache for parsers to avoid recreating them.
_parser_cache: Dict[str, Tuple[int, Language, object]] = {}
# Locks to serialize access to each cached parser (since Tree‑sitter parser instances are not thread‑safe).
_parser_locks: Dict[str, threading.Lock] = {}

def tree_sitter_logger(log_type: int, message: str) -> None:
    """
    Custom logger callback for the Tree-sitter parser.
    
    Args:
        log_type (int): The log type passed by Tree-sitter (e.g. LogType.LEX or LogType.PARSE).
        message (str): The detailed log message.
    """
    if log_type == LogType.LEX:
        log(f"Tree-sitter [LEX]: {message}", level="debug")
    elif log_type == LogType.PARSE:
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
        # Ensure a lock exists for this language.
        if language_name not in _parser_locks:
            _parser_locks[language_name] = threading.Lock()

        if language_name in _parser_cache:
            return _parser_cache[language_name]
        
        # Create new parser components.
        binding = get_binding(language_name)  # int pointer to the C binding.
        language = get_language(language_name)  # Tree-sitter Language instance.
        parser = get_parser(language_name)      # Tree-sitter Parser instance.

        # Attach our custom logger callback if enabled.
        if ATTACH_LOGGER_CALLBACK:
            try:
                parser.logger = tree_sitter_logger
            except Exception as e:
                log(f"Failed to attach logger to parser for {language_name}: {e}", level="warning")

        parser_tuple = (binding, language, parser)
        _parser_cache[language_name] = parser_tuple
        return parser_tuple
        
    except Exception as e:
        log(f"Could not get parser for language {language_name}: {e}", level="warning")
        return None

def parse_code(source_code: str, language_name: str) -> Optional[Node]:
    """
    Parse source code using tree-sitter.
    
    Args:
        source_code: Source code to parse.
        language_name: Programming language of the source.
        
    Returns:
        Root node of the AST or None if parsing failed.
    """
    try:
        parser_components = get_parser_for_language(language_name)
        if not parser_components:
            return None
            
        _, _, parser = parser_components

        # Protect the call to parser.parse with a language-specific lock to prevent concurrent access.
        lock = _parser_locks.get(language_name)
        if lock is None:
            # This should not occur but is a safe fallback.
            lock = threading.Lock()
            _parser_locks[language_name] = lock

        with lock:
            tree = parser.parse(bytes(source_code, "utf8"))
        return tree.root_node
        
    except Exception as e:
        log(f"Error parsing {language_name} code: {e}", level="error")
        return None

def get_ast_sexp(node) -> str:
    """
    Convert a Tree-sitter AST node to an S-expression string representation.
    Tries to use the native tree-sitter method if available, otherwise falls back
    to a custom implementation.
    
    This is in line with Tree-sitter's suggestions to use its native methods when possible
    ([1](https://tree-sitter.github.io/tree-sitter/print.html)) while providing our own fallback
    for languages where a dedicated query pattern isn't provided.
    """
    if not node:
        return "()"
    # Attempt to use the native method if available.
    if hasattr(node, "sexp") and callable(node.sexp):
        try:
            return node.sexp()
        except Exception as native_ex:
            log(f"Native sexp method failed: {native_ex}", level="debug")
    return _custom_get_ast_sexp(node)

def _custom_get_ast_sexp(node) -> str:
    """
    Recursively create an s-expression for the given AST node.
    This custom implementation is our fallback when a native method is not available.
    """
    result = f"({node.type}"
    if node.children:
        for child in node.children:
            # Safely attempt to retrieve the field name.
            field_name = getattr(child, "field_name", None)
            if field_name:
                result += f" {field_name}: "
            result += " " + _custom_get_ast_sexp(child)
    elif node.is_named:
        try:
            # Decode text safely from bytes.
            text = node.text.decode('utf-8', errors='replace')
        except Exception as decode_ex:
            text = "<decode-error>"
            log(f"Error decoding node text: {decode_ex}", level="error")
        result += f" {text!r}"
    result += ")"
    return result

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

def is_language_supported(language_name: str) -> bool:
    """
    Check if a language is supported by Tree-sitter.
    
    Args:
        language_name: Name of language to check.
        
    Returns:
        True if the language is supported, False otherwise.
    """
    try:
        get_binding(language_name)
        get_language(language_name)
        get_parser(language_name)
        return True
    except Exception:
        return False