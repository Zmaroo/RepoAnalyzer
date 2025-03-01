"""Tree-sitter based code parsing."""

from typing import Dict, Set, Optional, Any, List
import hashlib
import asyncio
from tree_sitter_language_pack import get_parser, get_language, SupportedLanguage
from utils.logger import log
from parsers.base_parser import BaseParser
from utils.error_handling import handle_errors, ProcessingError, ErrorBoundary
from parsers.language_mapping import TREE_SITTER_LANGUAGES
from parsers.models import PatternMatch, ProcessedPattern
from parsers.types import FileType, ParserType
from utils.cache import ast_cache

class TreeSitterError(ProcessingError):
    """Tree-sitter specific errors."""
    pass

class TreeSitterParser(BaseParser):
    """Tree-sitter implementation of the base parser."""
    
    def __init__(self, language_id: str, file_type: FileType):
        super().__init__(language_id, file_type, parser_type=ParserType.TREE_SITTER)
        self._language = None
        
        # Initialize the block extractor
        from parsers.block_extractor import block_extractor
        self.block_extractor = block_extractor
        
    def initialize(self) -> bool:
        with ErrorBoundary(f"initialize_tree_sitter_{self.language_id}", error_types=(Exception,)):
            self._language = get_parser(self.language_id)
            self._initialized = True
            return True
        
        return False

    @handle_errors(error_types=(LookupError, TreeSitterError))
    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """[3.1] Generate AST using tree-sitter with caching."""
        # Create a unique cache key based on language and source code hash
        source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
        cache_key = f"ast:{self.language_id}:{source_hash}"
        
        # First try to get from cache
        cached_ast = asyncio.run(ast_cache.get_async(cache_key))
        if cached_ast and "tree" in cached_ast:
            log(f"AST cache hit for {self.language_id}", level="debug")
            
            # For methods that need the root node, we'll need to generate it
            # But for most pattern processing, the tree dictionary is sufficient
            if self._language:
                with ErrorBoundary("regenerate_root_node_from_cache", error_types=(Exception,)):
                    # If needed, regenerate the root node
                    tree = self._language.parse(source_code.encode("utf8"))
                    root_node = tree.root_node
                    
                    # Return both the cached tree and the fresh root node
                    return {
                        "root": root_node,
                        "tree": cached_ast["tree"]
                    }
                # Fall back to just using the cached tree if ErrorBoundary caught an exception
                return cached_ast
            return cached_ast
        
        # If not in cache, generate the AST
        with ErrorBoundary("generate_ast", error_types=(Exception,)):
            tree = self._language.parse(source_code.encode("utf8"))
            root_node = tree.root_node
            
            # Full AST with root node (not serializable for caching)
            ast_dict = {
                "root": root_node,
                "tree": self._convert_tree_to_dict(root_node)
            }
            
            # Only cache the tree part since the root node is not serializable
            cache_data = {
                "tree": ast_dict["tree"]
            }
            
            # Store in cache asynchronously
            asyncio.run(ast_cache.set_async(cache_key, cache_data))
            log(f"AST cached for {self.language_id}", level="debug")
            
            return ast_dict
        
        log(f"Error in tree-sitter parsing for {self.language_id}", level="error")
        return {}

    def _process_pattern(
        self, 
        ast: Dict[str, Any], 
        source_code: str,
        pattern: ProcessedPattern
    ) -> List[PatternMatch]:
        """Process tree-sitter specific patterns."""
        if not pattern:
            return []
        
        # Check if we need to generate a root node because we're using a cached AST
        if "root" not in ast and "tree" in ast:
            log(f"Regenerating root node for pattern processing", level="debug")
            with ErrorBoundary(f"regenerate_root_node_{self.language_id}", error_types=(Exception,)):
                tree = self._language.parse(source_code.encode("utf8"))
                root_node = tree.root_node
                ast["root"] = root_node
        
        # If still no root node, we can't process the pattern
        if "root" not in ast:
            log(f"No root node available for pattern processing", level="warning")
            return []
        
        with ErrorBoundary(f"process_pattern_{pattern.pattern_name}", error_types=(Exception,)):
            query = self._language.query(pattern.pattern_name)
            matches = []
            for capture in query.captures(ast["root"]):
                capture_name, node = capture
                
                # Extract the actual text content using the block extractor for more precise extraction
                extracted_block = self.block_extractor.extract_block(
                    self.language_id, source_code, node)
                
                text = node.text.decode('utf8')  # Default text extraction
                if extracted_block:
                    # Use the more precisely extracted text if available
                    text = extracted_block.content
                
                match = PatternMatch(
                    text=text,
                    start=node.start_point,
                    end=node.end_point,
                    metadata={
                        "capture": capture_name,
                        "type": node.type
                    }
                )
                matches.append(match)
            return matches
        
        return []

    def _get_syntax_errors(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract syntax errors from tree-sitter node."""
        if "root" not in ast:
            # For a cached AST, we might not have the root node
            # We'll need to skip syntax error detection
            log("Cannot check syntax errors without root node", level="debug")
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
        
    def _extract_code_patterns(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns from AST using tree-sitter.
        This implementation overrides the base method to provide tree-sitter specific extraction.
        """
        patterns = []
        
        with ErrorBoundary("extract_code_patterns_tree_sitter", error_types=(Exception,)):
            # Ensure we have a root node
            if "root" not in ast and self._language:
                # Regenerate the root node if needed
                tree = self._language.parse(source_code.encode("utf8"))
                ast["root"] = tree.root_node
            
            if "root" not in ast:
                return patterns
                
            root_node = ast["root"]
            
            # Extract function definitions
            try:
                # Create a language-specific query for functions
                function_query = """
                    (function_definition) @function
                """
                
                # Adjust query based on language
                if self.language_id == "python":
                    function_query = """
                        (function_definition
                          name: (identifier) @function.name
                          body: (block) @function.body) @function
                    """
                elif self.language_id in ["javascript", "typescript"]:
                    function_query = """
                        (function_declaration
                          name: (identifier) @function.name
                          body: (statement_block) @function.body) @function
                    """
                elif self.language_id in ["cpp", "c"]:
                    function_query = """
                        (function_definition
                          declarator: (function_declarator
                            declarator: (identifier) @function.name)
                          body: (compound_statement) @function.body) @function
                    """
                
                # Execute the query
                query = self._language.query(function_query)
                
                for capture in query.captures(root_node):
                    capture_name, node = capture
                    
                    if capture_name == "function":
                        # Extract the function using the block extractor
                        block = self.block_extractor.extract_block(
                            self.language_id, source_code, node)
                        
                        if block and block.content:
                            # Try to find the function name
                            function_name = "unnamed_function"
                            for name_capture in query.captures(node):
                                name_capture_name, name_node = name_capture
                                if name_capture_name == "function.name":
                                    function_name = name_node.text.decode('utf8')
                                    break
                            
                            patterns.append({
                                'name': f'function_{function_name}',
                                'content': block.content,
                                'pattern_type': 'FUNCTION_DEFINITION',
                                'language': self.language_id,
                                'confidence': 0.95,
                                'metadata': {
                                    'type': 'function',
                                    'name': function_name,
                                    'node_type': node.type
                                }
                            })
            except Exception as e:
                log(f"Error extracting function patterns: {str(e)}", level="error")
            
            # Extract class definitions
            try:
                # Create a language-specific query for classes
                class_query = """
                    (class_definition) @class
                """
                
                # Adjust query based on language
                if self.language_id == "python":
                    class_query = """
                        (class_definition
                          name: (identifier) @class.name
                          body: (block) @class.body) @class
                    """
                elif self.language_id in ["javascript", "typescript"]:
                    class_query = """
                        (class_declaration
                          name: (identifier) @class.name
                          body: (class_body) @class.body) @class
                    """
                elif self.language_id in ["cpp", "c"]:
                    class_query = """
                        (class_specifier
                          name: (type_identifier) @class.name
                          body: (field_declaration_list) @class.body) @class
                    """
                
                # Execute the query
                query = self._language.query(class_query)
                
                for capture in query.captures(root_node):
                    capture_name, node = capture
                    
                    if capture_name == "class":
                        # Extract the class using the block extractor
                        block = self.block_extractor.extract_block(
                            self.language_id, source_code, node)
                        
                        if block and block.content:
                            # Try to find the class name
                            class_name = "unnamed_class"
                            for name_capture in query.captures(node):
                                name_capture_name, name_node = name_capture
                                if name_capture_name == "class.name":
                                    class_name = name_node.text.decode('utf8')
                                    break
                            
                            patterns.append({
                                'name': f'class_{class_name}',
                                'content': block.content,
                                'pattern_type': 'CLASS_DEFINITION',
                                'language': self.language_id,
                                'confidence': 0.95,
                                'metadata': {
                                    'type': 'class',
                                    'name': class_name,
                                    'node_type': node.type
                                }
                            })
            except Exception as e:
                log(f"Error extracting class patterns: {str(e)}", level="error")
        
        return patterns 