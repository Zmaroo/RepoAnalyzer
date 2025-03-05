"""Custom parser for INI files with enhanced documentation features."""

from typing import Dict, List, Any, Optional
import asyncio
import configparser
from parsers.base_parser import BaseParser
from parsers.types import FileType, ParserType, PatternCategory
from parsers.query_patterns.ini import INI_PATTERNS
from parsers.models import IniNode, PatternType
from utils.logger import log
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError, ParsingError, ErrorSeverity, handle_async_errors, AsyncErrorBoundary
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
import re
from collections import Counter

class IniParser(BaseParser):
    """Parser for INI files."""
    
    def __init__(self, language_id: str = "ini", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        self._initialized = False
        self._pending_tasks: set[asyncio.Future] = set()
        self.patterns = self._compile_patterns(INI_PATTERNS)
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("INI parser initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    log("INI parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing INI parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> IniNode:
        """Create a standardized INI AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return IniNode(**node_dict)

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse INI content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="INI parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                lines = source_code.splitlines()
                ast = self._create_node(
                    "document",
                    [0, 0],
                    [len(lines) - 1, len(lines[-1]) if lines else 0]
                )
                
                # Process comments first
                current_comment_block = []
                for i, line in enumerate(lines):
                    line_start = [i, 0]
                    line_end = [i, len(line)]
                    if comment_match := re.match(r'^\s*[;#]\s*(.*)$', line):
                        current_comment_block.append(comment_match.group(1).strip())
                        continue
                    if line.strip() and current_comment_block:
                        node = self._create_node(
                            "comment_block",
                            [i - len(current_comment_block), 0],
                            [i - 1, len(current_comment_block[-1])],
                            content="\n".join(current_comment_block)
                        )
                        ast.children.append(node)
                        current_comment_block = []
                
                # Parse INI structure
                try:
                    config = configparser.ConfigParser(allow_no_value=True)
                    future = submit_async_task(config.read_string, source_code)
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                        root_node = self._process_config(config, [0, 0])
                        ast.children.append(root_node)
                    finally:
                        self._pending_tasks.remove(future)
                except configparser.Error as e:
                    log(f"Error parsing INI structure: {e}", level="error")
                    ast.metadata["parse_error"] = str(e)
                
                # Handle any remaining comments
                if current_comment_block:
                    ast.metadata["trailing_comments"] = current_comment_block
                
                return ast.__dict__
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing INI content: {e}", level="error")
                return IniNode(
                    type="document", start_point=[0, 0], end_point=[0, 0],
                    error=str(e), children=[]
                ).__dict__
    
    def _process_config(self, config: configparser.ConfigParser, start_point: List[int]) -> IniNode:
        """Process a ConfigParser object into a node structure."""
        node = self._create_node(
            "root",
            start_point,
            [start_point[0], start_point[1] + 1],
            sections=list(config.sections())
        )
        
        # Process default section first
        if config.defaults():
            default_node = self._create_node(
                "section",
                start_point,
                [start_point[0], start_point[1] + 1],
                name="DEFAULT",
                options=list(config.defaults().keys())
            )
            for key, value in config.defaults().items():
                option_node = self._create_node(
                    "option",
                    [start_point[0], start_point[1] + 1],
                    [start_point[0], start_point[1] + len(key) + len(str(value)) + 3],
                    key=key,
                    value=value
                )
                default_node.children.append(option_node)
            node.children.append(default_node)
        
        # Process other sections
        for section in config.sections():
            section_node = self._create_node(
                "section",
                [start_point[0], start_point[1] + 1],
                [start_point[0], start_point[1] + len(section) + 2],
                name=section,
                options=list(config.options(section))
            )
            
            for key in config.options(section):
                value = config.get(section, key)
                option_node = self._create_node(
                    "option",
                    [start_point[0], start_point[1] + 1],
                    [start_point[0], start_point[1] + len(key) + len(str(value)) + 3],
                    key=key,
                    value=value
                )
                section_node.children.append(option_node)
            
            node.children.append(section_node)
        
        return node
    
    @handle_errors(error_types=(ParsingError, ProcessingError))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from INI files for repository learning.
        
        Args:
            source_code: The content of the INI file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()
            
        with ErrorBoundary(operation_name="INI pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                patterns = []
                
                # Parse the source first to get a structured representation
                future = submit_async_task(self._parse_source(source_code))
                self._pending_tasks.add(future)
                try:
                    ast = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                
                # Extract section patterns
                section_patterns = self._extract_section_patterns(ast)
                for section in section_patterns:
                    patterns.append({
                        'name': f'ini_section_{section["name"]}',
                        'content': section["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.9,
                        'metadata': {
                            'type': 'section',
                            'name': section["name"],
                            'options': section.get("options", [])
                        }
                    })
                
                # Extract option patterns
                option_patterns = self._extract_option_patterns(ast)
                for option in option_patterns:
                    patterns.append({
                        'name': f'ini_option_{option["type"]}',
                        'content': option["content"],
                        'pattern_type': PatternType.CODE_STRUCTURE,
                        'language': self.language_id,
                        'confidence': 0.85,
                        'metadata': {
                            'type': 'option',
                            'value_type': option["value_type"],
                            'examples': option.get("examples", [])
                        }
                    })
                
                # Extract comment patterns
                comment_patterns = self._extract_comment_patterns(ast)
                for comment in comment_patterns:
                    patterns.append({
                        'name': f'ini_comment_{comment["type"]}',
                        'content': comment["content"],
                        'pattern_type': PatternType.DOCUMENTATION,
                        'language': self.language_id,
                        'confidence': 0.8,
                        'metadata': {
                            'type': 'comment',
                            'style': comment["type"]
                        }
                    })
                
                return patterns
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error extracting patterns from INI file: {str(e)}", level="error")
                return []
    
    async def cleanup(self):
        """Clean up INI parser resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("INI parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up INI parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                properties = []
                
                # Extract properties from this section
                for child in node.get('children', []):
                    if isinstance(child, dict) and child.get('type') == 'option':
                        properties.append({
                            'key': child.get('key', ''),
                            'value': child.get('value', '')
                        })
                
                section_name = node.get('name', '')
                if section_name:
                    sections.append({
                        'name': section_name,
                        'content': f"[{section_name}]\n" + "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                        'options': properties
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_option_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common property patterns from the AST."""
        property_categories = {}
        
        def collect_properties(node, categories=None):
            if categories is None:
                categories = {}
                
            if isinstance(node, dict):
                # Check properties directly
                if node.get('type') == 'option':
                    key = node.get('key', '').lower()
                    value = node.get('value', '')
                    
                    # Categorize properties
                    if any(term in key for term in ['host', 'server', 'url', 'endpoint']):
                        category = 'connection'
                    elif any(term in key for term in ['user', 'password', 'auth', 'token', 'key', 'secret']):
                        category = 'authentication'
                    elif any(term in key for term in ['log', 'debug', 'verbose', 'trace']):
                        category = 'logging'
                    elif any(term in key for term in ['dir', 'path', 'file', 'folder']):
                        category = 'filesystem'
                    elif any(term in key for term in ['port', 'timeout', 'retry', 'max', 'min']):
                        category = 'connection_params'
                    elif any(term in key for term in ['enable', 'disable', 'toggle', 'feature']):
                        category = 'feature_flags'
                    else:
                        category = 'other'
                        
                    if category not in categories:
                        categories[category] = []
                        
                    categories[category].append({
                        'key': key,
                        'value': value
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_properties(child, categories)
                    
            return categories
            
        # Collect properties by category
        property_categories = collect_properties(ast)
        
        # Create patterns for each category
        patterns = []
        for category, properties in property_categories.items():
            if properties:  # Only include non-empty categories
                patterns.append({
                    'category': category,
                    'content': "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                    'value_type': category,
                    'examples': properties[:3]
                })
                
        return patterns
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def collect_comments(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    comments.append({
                        'type': 'block',
                        'content': node.get('content', '')
                    })
                elif node.get('type') == 'comment':
                    comments.append({
                        'type': 'inline',
                        'content': node.get('content', '')
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_comments(child)
                    
        collect_comments(ast)
        
        return comments
        
    def _detect_naming_conventions(self, names: List[str]) -> List[str]:
        """Detect naming conventions in a list of names."""
        if not names:
            return []
            
        conventions = []
        
        # Check for camelCase
        if any(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name) for name in names):
            conventions.append("camelCase")
            
        # Check for snake_case
        if any(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("snake_case")
            
        # Check for kebab-case
        if any(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name for name in names):
            conventions.append("kebab-case")
            
        # Check for PascalCase
        if any(re.match(r'^[A-Z][a-zA-Z0-9]*$', name) for name in names):
            conventions.append("PascalCase")
            
        # Check for UPPER_CASE
        if any(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("UPPER_CASE")
            
        # Check for lowercase
        if any(re.match(r'^[a-z][a-z0-9]*$', name) for name in names):
            conventions.append("lowercase")
            
        # Determine the most common convention
        if conventions:
            convention_counts = Counter(
                convention for name in names for convention in conventions 
                if self._matches_convention(name, convention)
            )
            
            if convention_counts:
                dominant_convention = convention_counts.most_common(1)[0][0]
                return [dominant_convention]
                
        return conventions
        
    def _matches_convention(self, name: str, convention: str) -> bool:
        """Check if a name matches a specific naming convention."""
        if convention == "camelCase":
            return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name))
        elif convention == "snake_case":
            return bool(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name)
        elif convention == "kebab-case":
            return bool(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name)
        elif convention == "PascalCase":
            return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
        elif convention == "UPPER_CASE":
            return bool(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name)
        elif convention == "lowercase":
            return bool(re.match(r'^[a-z][a-z0-9]*$', name))
        return False 