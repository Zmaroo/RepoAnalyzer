"""Custom parser implementations.

This module provides custom parser implementations for languages that don't have
tree-sitter support or where a custom implementation is preferred.

Each parser must:
1. Inherit from BaseParser
2. Implement parse() method
3. Handle initialization and cleanup
4. Support async operations
"""

import asyncio
from typing import Dict, Type, Set
from parsers.base_parser import BaseParser
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task

# Import all custom parser classes
from .custom_asciidoc_parser import AsciidocParser
from .custom_cobalt_parser import CobaltParser
from .custom_editorconfig_parser import EditorconfigParser
from .custom_env_parser import EnvParser
from .custom_graphql_parser import GraphQLParser
from .custom_html_parser import HTMLParser
from .custom_ini_parser import IniParser
from .custom_json_parser import JsonParser
from .custom_markdown_parser import MarkdownParser
from .custom_nim_parser import NimParser
from .custom_ocaml_parser import OcamlParser
from .custom_plaintext_parser import PlaintextParser
from .custom_rst_parser import RstParser
from .custom_toml_parser import TomlParser
from .custom_xml_parser import XmlParser
from .custom_yaml_parser import YamlParser

# Map of language IDs to parser classes
CUSTOM_PARSER_CLASSES: Dict[str, Type[BaseParser]] = {
    'asciidoc': AsciidocParser,
    'cobalt': CobaltParser,
    'editorconfig': EditorconfigParser,
    'env': EnvParser,
    'graphql': GraphQLParser,
    'html': HTMLParser,
    'ini': IniParser,
    'json': JsonParser,
    'markdown': MarkdownParser,
    'nim': NimParser,
    'ocaml': OcamlParser,
    'plaintext': PlaintextParser,
    'rst': RstParser,
    'toml': TomlParser,
    'xml': XmlParser,
    'yaml': YamlParser
}

# Track initialization state
_initialized = False
_pending_tasks: Set[asyncio.Future] = set()
_initialized_parsers: Dict[str, BaseParser] = {}

@handle_async_errors(error_types=(Exception,))
async def initialize_custom_parsers():
    """Initialize all custom parser resources."""
    global _initialized
    
    if _initialized:
        return
    
    try:
        async with AsyncErrorBoundary("custom parsers initialization"):
            # Initialize commonly used parsers first
            common_parsers = {'markdown', 'json', 'yaml', 'html', 'xml'}
            for language in common_parsers:
                if language in CUSTOM_PARSER_CLASSES:
                    parser_cls = CUSTOM_PARSER_CLASSES[language]
                    parser = parser_cls(language)
                    future = submit_async_task(parser.initialize())
                    _pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                        _initialized_parsers[language] = parser
                    finally:
                        _pending_tasks.remove(future)
            
            _initialized = True
            log("Custom parsers initialized", level="info")
    except Exception as e:
        log(f"Error initializing custom parsers: {e}", level="error")
        raise

async def cleanup_custom_parsers():
    """Clean up all custom parser resources."""
    global _initialized
    
    try:
        # Clean up all initialized parsers
        cleanup_tasks = []
        
        for parser in _initialized_parsers.values():
            future = submit_async_task(parser.cleanup())
            cleanup_tasks.append(future)
        
        # Wait for all cleanup tasks
        await asyncio.gather(*[asyncio.wrap_future(f) for f in cleanup_tasks], return_exceptions=True)
        
        # Clean up any remaining pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*[asyncio.wrap_future(f) for f in _pending_tasks], return_exceptions=True)
            _pending_tasks.clear()
        
        # Clear initialized parsers
        _initialized_parsers.clear()
        
        _initialized = False
        log("Custom parsers cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up custom parsers: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup_custom_parsers)

# Export all parser classes and initialization functions
__all__ = [
    'CUSTOM_PARSER_CLASSES',
    'initialize_custom_parsers',
    'cleanup_custom_parsers',
    'AsciidocParser',
    'CobaltParser',
    'EditorconfigParser',
    'EnvParser',
    'GraphQLParser',
    'HTMLParser',
    'IniParser',
    'JsonParser',
    'MarkdownParser',
    'NimParser',
    'OcamlParser',
    'PlaintextParser',
    'RstParser',
    'TomlParser',
    'XmlParser',
    'YamlParser'
] 