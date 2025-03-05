"""
Custom parsers for various file types that don't have tree-sitter support.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Type
from parsers.types import FileType
from parsers.base_parser import BaseParser
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity
import importlib
import inspect
import os
import sys

# Dictionary to hold all custom parsers
_parsers: Dict[str, Type[BaseParser]] = {}

@handle_errors(error_types=(ProcessingError,))
def _load_parsers():
    """Dynamically load all custom parser modules."""
    parser_dir = Path(__file__).parent
    for file in parser_dir.glob("custom_*.py"):
        if file.name == "__init__.py":
            continue
            
        module_name = file.stem
        with ErrorBoundary(operation_name=f"loading parser module {module_name}", error_types=(ImportError, AttributeError), severity=ErrorSeverity.ERROR):
            try:
                # Import the module
                module = importlib.import_module(f"parsers.custom_parsers.{module_name}")
                
                # Find parser classes
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, BaseParser) and obj != BaseParser):
                        language_id = getattr(obj, "LANGUAGE_ID", None) or module_name.replace("custom_", "")
                        _parsers[language_id] = obj
                        log(f"Registered custom parser for: {language_id}", level="debug")
            except (ImportError, AttributeError, TypeError) as e:
                log(f"Failed to load custom parser {module_name}: {e}", level="error")
                # Continue loading other parsers even if one fails

def get_parser(language_id: str, file_type: Optional[FileType] = None) -> Optional[BaseParser]:
    """
    Get a custom parser instance for the given language ID.
    
    Args:
        language_id: The language identifier (like 'markdown', 'ini', etc.)
        file_type: Optional file type to initialize the parser with
        
    Returns:
        A parser instance if available, None otherwise
    """
    if not _parsers:
        _load_parsers()
        
    parser_class = _parsers.get(language_id)
    if parser_class:
        # Create a default FileType if None is provided
        actual_file_type = file_type if file_type is not None else FileType.CODE
        return parser_class(language_id, actual_file_type)
    return None

# Ensure all parsers have pattern extraction functionality
def ensure_pattern_extraction():
    """
    Ensure all custom parsers have pattern extraction functionality.
    If they don't have an extract_patterns method, add a default implementation.
    """
    if not _parsers:
        _load_parsers()
        
    for language_id, parser_class in _parsers.items():
        if not hasattr(parser_class, 'extract_patterns'):
            log(f"Adding default pattern extraction to {language_id} parser", level="debug")
            
            # Add default pattern extraction method
            def default_extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
                """Default pattern extraction implementation."""
                return []
                
            parser_class.extract_patterns = default_extract_patterns

# Load parsers on module import
_load_parsers()
ensure_pattern_extraction()

from typing import Dict, Type
from parsers.base_parser import BaseParser

from .custom_env_parser import EnvParser
from .custom_plaintext_parser import PlaintextParser
from .custom_yaml_parser import YamlParser
from .custom_markdown_parser import MarkdownParser
from .custom_editorconfig_parser import EditorconfigParser
from .custom_graphql_parser import GraphqlParser
from .custom_nim_parser import NimParser
from .custom_ocaml_parser import OcamlParser
from .custom_cobalt_parser import CobaltParser
from .custom_xml_parser import XmlParser
from .custom_html_parser import HtmlParser
from .custom_ini_parser import IniParser
from .custom_json_parser import JsonParser
from .custom_rst_parser import RstParser
from .custom_toml_parser import TomlParser
from .custom_asciidoc_parser import AsciidocParser

# Register custom parser classes
CUSTOM_PARSER_CLASSES: Dict[str, Type[BaseParser]] = {
    "env": EnvParser,
    "plaintext": PlaintextParser,
    "yaml": YamlParser,
    "markdown": MarkdownParser,
    "editorconfig": EditorconfigParser,
    "graphql": GraphqlParser,
    "nim": NimParser,
    "ocaml": OcamlParser,
    "ocaml_interface": OcamlParser,
    "cobalt": CobaltParser,
    "xml": XmlParser,
    "html": HtmlParser,
    "ini": IniParser,
    "json": JsonParser,
    "restructuredtext": RstParser,
    "toml": TomlParser,
    "asciidoc": AsciidocParser
}

# Export the parser classes
__all__ = [
    'CUSTOM_PARSER_CLASSES',
    'EnvParser',
    'PlaintextParser',
    'YamlParser',
    'MarkdownParser',
    'EditorconfigParser',
    'GraphqlParser',
    'NimParser',
    'OcamlParser',
    'CobaltParser',
    'XmlParser',
    'HtmlParser',
    'IniParser',
    'JsonParser',
    'RstParser',
    'TomlParser',
    'AsciidocParser'
] 