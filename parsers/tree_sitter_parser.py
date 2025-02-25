"""Tree-sitter based code parsing."""

from typing import Dict, Set, Optional, Any, List
from tree_sitter_language_pack import get_parser, get_language, SupportedLanguage
from utils.logger import log
from parsers.base_parser import BaseParser
from utils.error_handling import handle_errors, ProcessingError
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from parsers.models import PatternMatch, ProcessedPattern
from parsers.types import FileType, ParserType

class TreeSitterError(ProcessingError):
    """Tree-sitter specific errors."""
    pass

class TreeSitterParser(BaseParser):
    """Tree-sitter implementation of the base parser."""
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type, parser_type=ParserType.TREE_SITTER)
        self._language = None
        
    def initialize(self) -> bool:
        try:
            self._language = get_parser(self.language_id)
            self._initialized = True
            return True
        except Exception as e:
            log(f"Failed to initialize tree-sitter for {self.language_id}: {e}", level="error")
            return False

    @handle_errors(error_types=(LookupError, TreeSitterError))
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """[3.1] Generate AST using tree-sitter."""
        try:
            tree = self._language.parse(source_code.encode("utf8"))
            root_node = tree.root_node
            return {
                "root": root_node,
                "tree": self._convert_tree_to_dict(root_node)
            }
        except Exception as e:
            log(f"Error in tree-sitter parsing for {self.language_id}: {e}", level="error")
            return {}

    def _process_pattern(
        self, 
        ast: Dict[str, Any], 
        source_code: str,
        pattern: ProcessedPattern
    ) -> List[PatternMatch]:
        """Process tree-sitter specific patterns."""
        if not pattern or "root" not in ast:
            return []
            
        try:
            query = self._language.query(pattern.pattern_name)
            matches = []
            for capture_name, node in query.captures(ast["root"]):
                match = PatternMatch(
                    text=node.text.decode('utf8'),
                    start=node.start_point,
                    end=node.end_point,
                    metadata={
                        "capture": capture_name,
                        "type": node.type
                    }
                )
                matches.append(match)
            return matches
        except Exception as e:
            log(f"Error processing pattern: {e}", level="error")
            return []

    def _get_syntax_errors(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract syntax errors from tree-sitter node."""
        if "root" not in ast:
            return []
        return self._get_syntax_errors_recursive(ast["root"])

    def _get_syntax_errors_recursive(self, node) -> List[Dict[str, Any]]:
        """Recursively collect syntax errors."""
        errors = []
        if node.has_error:
            errors.append({
                'type': node.type,
                'start': node.start_point,
                'end': node.end_point,
                'is_missing': node.is_missing
            })
        for child in node.children:
            errors.extend(self._get_syntax_errors_recursive(child))
        return errors

    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert tree-sitter node to dict."""
        return {
            'type': node.type,
            'start': node.start_point,
            'end': node.end_point,
            'text': node.text.decode('utf8') if len(node.children) == 0 else None,
            'children': [self._convert_tree_to_dict(child) for child in node.children] if node.children else []
        }

    def get_supported_languages(self) -> Set[str]:
        """Get set of supported languages."""
        return TREE_SITTER_LANGUAGES.copy() 