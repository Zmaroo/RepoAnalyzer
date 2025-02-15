"""Language parser module using tree-sitter with custom logger callback."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from tree_sitter import Language, Node, LogType
from typing import Optional, Dict, Tuple
from utils.logger import log  # Use the common logger
import os
import threading
from parsers.language_mapping import (
    normalize_language_name, 
    LanguageSupport,
    EXTENSION_TO_LANGUAGE,
    CUSTOM_PARSER_FUNCTIONS
)
from parsers.common_parser_utils import build_parser_output, extract_features_from_ast

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
        
        # Create new parser components.
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

        # Attach our custom logger callback if enabled.
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

# Define a simple wrapper for custom AST dictionaries to emulate a tree-sitter AST node.
class CustomASTNode:
    def __init__(self, ast_dict: dict, features: dict = None):
        self.ast_dict = ast_dict
        self.features = features or {}

    @property
    def type(self):
        # Assuming your custom parser returns a key "type" for the root;
        # if not present, we default to a string indicating custom.
        return self.ast_dict.get("type", "custom")
    
    @property
    def json_ast(self) -> str:
        """
        Returns the JSON-serialized form of the AST.
        This is useful for storage and cross-system exchange.
        """
        import json
        return json.dumps(self.ast_dict)

    def __getattr__(self, attr):
        # Delegate attribute access to the dictionary.
        return self.ast_dict.get(attr, None)

    def __repr__(self):
        return f"<CustomASTNode type={self.type} features={list(self.features.keys())}>"

def parse_code(source_code: str, language: str) -> dict:
    """
    Parse the source code using a custom parser if available;
    otherwise, fall back to Tree‑sitter parsing and produce a standardized output.
    
    Returns:
        dict: A dictionary with the following keys:
            - content: the raw source code,
            - language: the normalized language,
            - ast_data: the AST as a dictionary,
            - ast_json: the JSON-serialized AST,
            - ast_features: features extracted from the AST,
            - lines_of_code: the total number of lines,
            - documentation: any supplementary doc content,
            - complexity: a computed complexity value.
    """
    from parsers.language_mapping import CUSTOM_PARSER_FUNCTIONS, normalize_language_name
    from parsers.common_parser_utils import build_parser_output, extract_features_from_ast
    normalized_language = normalize_language_name(language)
    
    # Use a custom parser if one is registered.
    if normalized_language in CUSTOM_PARSER_FUNCTIONS:
        return CUSTOM_PARSER_FUNCTIONS[normalized_language](source_code)
    else:
        # Fall back to Tree‑sitter parsing.
        from tree_sitter_language_pack import get_parser
        parser = get_parser(normalized_language)
        if parser is None:
            from utils.logger import log
            log(f"Tree-sitter parser not available for language {normalized_language}", level="error")
            return None
        tree = parser.parse(source_code.encode("utf-8"))
        root = tree.root_node if hasattr(tree, "root_node") else tree
        
        # Use our helper to convert the Node to a dictionary.
        ast_data = get_ast_json(root)
        
        try:
            features = extract_features_from_ast(ast_data)
        except Exception as e:
            from utils.logger import log
            log(f"Error extracting AST features: {e}", level="error")
            features = {}
        
        return build_parser_output(
            source_code=source_code,
            language=normalized_language,
            ast=ast_data,
            features=features,
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=1
        )

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