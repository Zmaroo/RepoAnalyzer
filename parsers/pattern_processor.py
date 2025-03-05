"""Unified pattern processing and query system."""

from typing import Dict, Any, List, Union, Callable, Optional, Set
from dataclasses import dataclass, field
import asyncio
from parsers.language_mapping import TREE_SITTER_LANGUAGES, CUSTOM_PARSER_LANGUAGES, normalize_language_name
import re
import time
from parsers.types import ParserType
from parsers.models import PatternDefinition, PatternMatch, FileClassification, PatternType
from utils.logger import log
import os
import importlib
from parsers.language_mapping import is_supported_language
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary, ErrorSeverity, handle_async_errors
from utils.cache import cache_coordinator
from utils.app_init import register_shutdown_handler
from utils.async_runner import submit_async_task
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator

# Try to import pattern statistics
try:
    from analytics.pattern_statistics import pattern_statistics
    PATTERN_STATS_ENABLED = True
except ImportError:
    PATTERN_STATS_ENABLED = False
    log("Pattern statistics module not available, statistics collection disabled", level="warning")

# Add these common patterns at the top level
COMMON_PATTERNS = {
    'comment_single': re.compile(r'//\s*(.+)$|#\s*(.+)$'),
    'comment_multi': re.compile(r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL),
    'metadata': re.compile(r'^@(\w+):\s*(.*)$'),
    'url': re.compile(r'https?://\S+|www\.\S+'),
    'email': re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b'),
    'path': re.compile(r'(?:^|[\s(])(?:/[\w.-]+)+|\b[\w.-]+/[\w.-/]+')
}

@dataclass
class CompiledPattern:
    """Holds compiled versions (tree-sitter and regex) of a pattern."""
    tree_sitter: Optional[str] = None
    regex: Optional[Union[str, re.Pattern]] = None
    extract: Optional[Callable] = None
    definition: Optional[PatternDefinition] = None
    _initialized: bool = False
    _pending_tasks: Set[asyncio.Future] = field(default_factory=set)

    def __post_init__(self):
        """Post initialization setup."""
        register_shutdown_handler(self.cleanup)

    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize pattern resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("pattern initialization"):
                    # No special initialization needed yet
                    self._initialized = True
                    return True
            except Exception as e:
                log(f"Error initializing pattern: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up pattern resources."""
        try:
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            self._initialized = False
        except Exception as e:
            log(f"Error cleaning up pattern: {e}", level="error")

def compile_patterns(pattern_defs: Dict[str, Any]) -> Dict[str, Any]:
    """Compile regex patterns from a pattern definitions dictionary."""
    compiled = {}
    for category, patterns in pattern_defs.items():
        for name, pattern_obj in patterns.items():
            with ErrorBoundary(f"compile_pattern_{name}", error_types=(Exception,)):
                compiled[name] = re.compile(pattern_obj.pattern, re.DOTALL)
    return compiled

class PatternProcessor:
    """Central pattern processing system."""
    
    def __init__(self):
        """Initialize the pattern processor."""
        # Initialize dictionaries for all supported languages first
        self._tree_sitter_patterns = {lang: {} for lang in TREE_SITTER_LANGUAGES}
        self._regex_patterns = {lang: {} for lang in CUSTOM_PARSER_LANGUAGES}
        
        # Used to track which language patterns have been loaded
        self._loaded_languages = set()
        
        # Import block extractor
        from parsers.block_extractor import block_extractor
        self.block_extractor = block_extractor
        
        # Track languages with tree-sitter support
        self.tree_sitter_languages = TREE_SITTER_LANGUAGES
        
        # Initialize state tracking
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self):
        """Initialize pattern processor resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("pattern processor initialization"):
                    # Initialize cache coordinator
                    future = submit_async_task(cache_coordinator.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    # Initialize upsert coordinator
                    future = submit_async_task(upsert_coordinator.initialize())
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    # Load initial patterns
                    for language in TREE_SITTER_LANGUAGES:
                        future = submit_async_task(self._ensure_patterns_loaded(language))
                        self._pending_tasks.add(future)
                        try:
                            await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                    
                    self._initialized = True
                    log("Pattern processor initialized", level="info")
            except Exception as e:
                log(f"Error initializing pattern processor: {e}", level="error")
                raise
    
    @handle_async_errors(error_types=(Exception,))
    async def _ensure_patterns_loaded(self, language: str):
        """Ensure patterns for a language are loaded."""
        if not self._initialized:
            await self.initialize()

        normalized_lang = normalize_language_name(language)
        
        # Skip if already loaded
        if normalized_lang in self._loaded_languages:
            return
            
        # Load the patterns based on parser type
        async with AsyncErrorBoundary(f"load_patterns_{normalized_lang}", error_types=(Exception,)):
            if normalized_lang in TREE_SITTER_LANGUAGES:
                await self._load_tree_sitter_patterns(normalized_lang)
            elif normalized_lang in CUSTOM_PARSER_LANGUAGES:
                await self._load_custom_patterns(normalized_lang)
                
            # Mark as loaded even if there were no patterns
            self._loaded_languages.add(normalized_lang)
    
    @handle_async_errors(error_types=(Exception,))
    async def _load_tree_sitter_patterns(self, language: str):
        """Load tree-sitter specific patterns for a language."""
        from parsers.query_patterns import get_patterns_for_language
        
        async with AsyncErrorBoundary(f"load_tree_sitter_patterns_{language}"):
            future = submit_async_task(get_patterns_for_language(language))
            self._pending_tasks.add(future)
            try:
                patterns = await asyncio.wrap_future(future)
                if patterns:
                    # Compile and initialize each pattern
                    for pattern_name, pattern in patterns.items():
                        compiled = CompiledPattern(
                            tree_sitter=pattern.get('pattern'),
                            extract=pattern.get('extract'),
                            definition=pattern.get('definition')
                        )
                        await compiled.initialize()
                        patterns[pattern_name] = compiled
                    
                    self._tree_sitter_patterns[language] = patterns
                    log(f"Loaded {len(patterns)} tree-sitter patterns for {language}", level="debug")
            finally:
                self._pending_tasks.remove(future)
    
    @handle_async_errors(error_types=(Exception,))
    async def _load_custom_patterns(self, language: str):
        """Load custom parser patterns for a language."""
        from parsers.query_patterns import get_patterns_for_language
        
        async with AsyncErrorBoundary(f"load_custom_patterns_{language}"):
            future = submit_async_task(get_patterns_for_language(language))
            self._pending_tasks.add(future)
            try:
                patterns = await asyncio.wrap_future(future)
                if patterns:
                    # Compile and initialize each pattern
                    for pattern_name, pattern in patterns.items():
                        compiled = CompiledPattern(
                            regex=re.compile(pattern['pattern'], re.DOTALL),
                            extract=pattern.get('extract'),
                            definition=pattern.get('definition')
                        )
                        await compiled.initialize()
                        patterns[pattern_name] = compiled
                    
                    self._regex_patterns[language] = patterns
                    log(f"Loaded {len(patterns)} regex patterns for {language}", level="debug")
            finally:
                self._pending_tasks.remove(future)

    @handle_async_errors(error_types=(Exception,))
    async def get_patterns_for_file(self, classification: FileClassification) -> dict:
        """
        Get patterns based on parser type and language.
        Ensures patterns are loaded before returning them.
        
        Args:
            classification: File classification containing language and parser type
            
        Returns:
            Dictionary of patterns for the specified language
        """
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(f"get_patterns_{classification.language_id}"):
            # Make sure patterns are loaded for this language
            await self._ensure_patterns_loaded(classification.language_id)
            
            # Return the appropriate pattern set
            patterns = (self._tree_sitter_patterns if classification.parser_type == ParserType.TREE_SITTER 
                       else self._regex_patterns)
            return patterns.get(classification.language_id, {})
        
    def validate_pattern(self, pattern: CompiledPattern, language: str) -> bool:
        """Validate pattern matches parser type."""
        is_tree_sitter = language in TREE_SITTER_LANGUAGES
        return is_tree_sitter == (pattern.definition.pattern_type == "tree-sitter")

    @handle_async_errors(error_types=(Exception,))
    async def process_node(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process a node using appropriate pattern type."""
        start_time = time.time()
        compilation_time = 0
        
        # Track compilation time if available
        if hasattr(pattern, 'compilation_time_ms'):
            compilation_time = pattern.compilation_time_ms
        
        if pattern.tree_sitter:
            matches = await self._process_tree_sitter_pattern(source_code, pattern)
        elif pattern.regex:
            matches = await self._process_regex_pattern(source_code, pattern)
        else:
            matches = []
        
        # Record statistics if enabled
        if PATTERN_STATS_ENABLED and hasattr(pattern, 'definition') and pattern.definition:
            execution_time_ms = (time.time() - start_time) * 1000
            pattern_id = getattr(pattern.definition, 'id', pattern.definition.name if hasattr(pattern.definition, 'name') else 'unknown')
            pattern_type = getattr(pattern.definition, 'pattern_type', PatternType.CODE_STRUCTURE)
            language = getattr(pattern.definition, 'language', 'unknown')
            
            # If pattern_type is a string, convert it to the enum
            if isinstance(pattern_type, str):
                try:
                    pattern_type = PatternType(pattern_type)
                except ValueError:
                    pattern_type = PatternType.CODE_STRUCTURE
            
            # Call the pattern statistics manager
            try:
                future = submit_async_task(pattern_statistics.track_pattern_execution(
                    pattern_id=pattern_id,
                    pattern_type=pattern_type,
                    language=language,
                    execution_time_ms=execution_time_ms,
                    compilation_time_ms=compilation_time,
                    matches_found=len(matches),
                    memory_bytes=len(source_code) if matches else 0  # Rough estimate
                ))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
            except Exception as e:
                log(f"Error tracking pattern statistics: {str(e)}", level="error")
        
        return matches

    @handle_async_errors(error_types=(Exception,))
    async def _process_regex_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using regex pattern."""
        start_time = time.time()
        matches = []
        
        # Submit regex processing as an async task
        future = submit_async_task(self._process_regex_matches(source_code, pattern, start_time))
        self._pending_tasks.add(future)
        try:
            matches = await asyncio.wrap_future(future)
        finally:
            self._pending_tasks.remove(future)
            
        return matches
        
    def _process_regex_matches(self, source_code: str, pattern: CompiledPattern, start_time: float) -> List[PatternMatch]:
        """Helper method to process regex matches in a separate task."""
        matches = []
        for match in pattern.regex.finditer(source_code):
            result = PatternMatch(
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                metadata={
                    "groups": match.groups(),
                    "named_groups": match.groupdict(),
                    "execution_time_ms": (time.time() - start_time) * 1000
                }
            )
            if pattern.extract:
                with ErrorBoundary("regex pattern extraction"):
                    result.metadata.update(pattern.extract(result))
            matches.append(result)
        return matches

    @handle_async_errors(error_types=(Exception,))
    async def _process_tree_sitter_pattern(self, source_code: str, pattern: CompiledPattern) -> List[PatternMatch]:
        """Process using tree-sitter pattern."""
        # Pre-import required modules outside the error boundary
        from tree_sitter_language_pack import get_parser
        from parsers.models import PatternMatch
        import hashlib
        
        start_time = time.time()
        matches = []
        
        async with AsyncErrorBoundary(f"tree_sitter_pattern_{pattern.language_id if hasattr(pattern, 'language_id') else 'unknown'}"):
            # Get the tree-sitter parser for this language
            parser = get_parser(pattern.language_id)
            if not parser:
                return []
            
            # Create a unique cache key based on language and source code hash
            source_hash = hashlib.md5(source_code.encode('utf8')).hexdigest()
            cache_key = f"ast:{pattern.language_id}:{source_hash}"
            
            # Try to get from cache
            future = submit_async_task(cache_coordinator.ast_cache.get_async(cache_key))
            self._pending_tasks.add(future)
            try:
                cached_ast = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
                
            if cached_ast and "tree" in cached_ast:
                log(f"Using cached AST for pattern processing", level="debug")
                
                # For pattern processing, we need the root node
                # Parse the source code to get the tree with root node
                future = submit_async_task(parser.parse(bytes(source_code, "utf8")))
                self._pending_tasks.add(future)
                try:
                    tree = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                    
                if not tree:
                    return []
            else:
                # Parse the source code if not in cache
                future = submit_async_task(parser.parse(bytes(source_code, "utf8")))
                self._pending_tasks.add(future)
                try:
                    tree = await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                    
                if not tree:
                    return []
                
                # Cache the AST for future use
                cache_data = {
                    "tree": self._convert_tree_to_dict(tree.root_node)
                }
                future = submit_async_task(cache_coordinator.ast_cache.set_async(cache_key, cache_data))
                self._pending_tasks.add(future)
                try:
                    await asyncio.wrap_future(future)
                finally:
                    self._pending_tasks.remove(future)
                log(f"AST cached for pattern processing", level="debug")
            
            # Execute the tree-sitter query
            query = parser.language.query(pattern.tree_sitter)
            
            # Process matches in a separate task
            future = submit_async_task(self._process_tree_sitter_matches(query, tree.root_node, pattern, start_time))
            self._pending_tasks.add(future)
            try:
                matches = await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
            
        return matches
        
    def _process_tree_sitter_matches(self, query, root_node, pattern: CompiledPattern, start_time: float) -> List[PatternMatch]:
        """Helper method to process tree-sitter matches in a separate task."""
        matches = []
        for match in query.matches(root_node):
            captures = {capture.name: capture.node for capture in match.captures}
            
            # Create a pattern match result
            result = PatternMatch(
                text=match.pattern_node.text.decode('utf8'),
                start=match.pattern_node.start_point,
                end=match.pattern_node.end_point,
                metadata={
                    "captures": captures,
                    "execution_time_ms": (time.time() - start_time) * 1000
                }
            )
            
            # Apply custom extraction if available
            if pattern.extract:
                with ErrorBoundary("pattern extraction"):
                    extracted = pattern.extract(result)
                    if extracted:
                        result.metadata.update(extracted)
            
            matches.append(result)
            
        return matches

    @handle_async_errors(error_types=(Exception,))
    async def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert tree-sitter node to dict asynchronously."""
        if not node:
            return {}
        
        # Process children asynchronously
        children = []
        if node.children:
            tasks = []
            for child in node.children:
                future = submit_async_task(self._convert_tree_to_dict(child))
                self._pending_tasks.add(future)
                tasks.append(future)
            
            try:
                children = await asyncio.gather(*[asyncio.wrap_future(f) for f in tasks])
            finally:
                for task in tasks:
                    self._pending_tasks.remove(task)
        
        return {
            'type': node.type,
            'start': node.start_point,
            'end': node.end_point,
            'text': node.text.decode('utf8') if len(node.children) == 0 else None,
            'children': children
        }

    @handle_async_errors(error_types=(Exception,))
    async def compile_patterns(self, pattern_defs: Dict[str, Any]) -> Dict[str, Any]:
        """Compile regex patterns from a pattern definitions dictionary asynchronously."""
        compiled = {}
        tasks = []
        
        for category, patterns in pattern_defs.items():
            for name, pattern_obj in patterns.items():
                future = submit_async_task(self._compile_single_pattern(name, pattern_obj))
                self._pending_tasks.add(future)
                tasks.append((name, future))
        
        try:
            for name, future in tasks:
                try:
                    pattern = await asyncio.wrap_future(future)
                    if pattern:
                        compiled[name] = pattern
                except Exception as e:
                    log(f"Error compiling pattern {name}: {str(e)}", level="error")
        finally:
            for _, task in tasks:
                self._pending_tasks.remove(task)
                
        return compiled
        
    def _compile_single_pattern(self, name: str, pattern_obj: Any) -> Optional[re.Pattern]:
        """Helper method to compile a single pattern in a separate task."""
        with ErrorBoundary(f"compile_pattern_{name}", error_types=(Exception,)):
            return re.compile(pattern_obj.pattern, re.DOTALL)

    @handle_async_errors(error_types=(Exception,))
    async def extract_repository_patterns(self, file_path: str, source_code: str, language: str) -> List[Dict[str, Any]]:
        """
        Extract patterns from source code for repository learning.
        
        Args:
            file_path: Path to the file (used for language detection if not specified)
            source_code: Source code content
            language: Programming language
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        async with AsyncErrorBoundary("extract_repository_patterns", error_types=(Exception,)):
            # Load the appropriate pattern set based on language
            from parsers.language_mapping import REPOSITORY_LEARNING_PATTERNS
            
            language_rules = REPOSITORY_LEARNING_PATTERNS.get(language, {})
            if not language_rules:
                log(f"No repository learning patterns defined for {language}", level="debug")
                return patterns
                
            # Extract different types of patterns
            structure_patterns = await self._extract_code_structure_patterns(
                source_code, language_rules, language)
            naming_patterns = await self._extract_naming_convention_patterns(
                source_code, language_rules)
            error_patterns = await self._extract_error_handling_patterns(
                source_code, language_rules, language)
            
            # Combine all patterns
            patterns.extend(structure_patterns)
            patterns.extend(naming_patterns)
            patterns.extend(error_patterns)
            
            # Try to extract patterns using tree-sitter if available
            if language in self.tree_sitter_languages:
                try:
                    from tree_sitter_language_pack import get_parser
                    import importlib
                    
                    # Check if we have REPOSITORY_LEARNING section in language patterns
                    pattern_module_name = f"parsers.query_patterns.{language}"
                    learning_patterns = None
                    
                    try:
                        pattern_module = importlib.import_module(pattern_module_name)
                        if hasattr(pattern_module, f"{language.upper()}_PATTERNS"):
                            pattern_dict = getattr(pattern_module, f"{language.upper()}_PATTERNS")
                            learning_patterns = pattern_dict.get("REPOSITORY_LEARNING", {})
                    except (ImportError, AttributeError):
                        pass
                    
                    if learning_patterns:
                        parser = get_parser(language)
                        future = submit_async_task(parser.parse(source_code.encode("utf8")))
                        self._pending_tasks.add(future)
                        try:
                            tree = await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                            
                        root_node = tree.root_node
                        
                        # Process each tree-sitter pattern for learning
                        for pattern_name, pattern_def in learning_patterns.items():
                            if 'pattern' in pattern_def and 'extract' in pattern_def:
                                try:
                                    query = parser.query(pattern_def['pattern'])
                                    
                                    # Process captures using our improved block extractor
                                    future = submit_async_task(self._process_tree_sitter_captures(
                                        query, root_node, pattern_name, pattern_def, language, source_code))
                                    self._pending_tasks.add(future)
                                    try:
                                        capture_patterns = await asyncio.wrap_future(future)
                                        patterns.extend(capture_patterns)
                                    finally:
                                        self._pending_tasks.remove(future)
                                except Exception as e:
                                    log(f"Error processing tree-sitter query for {pattern_name}: {str(e)}", level="error")
                except Exception as e:
                    log(f"Error using tree-sitter for pattern extraction: {str(e)}", level="error")
            
        return patterns
        
    def _process_tree_sitter_captures(self, query, root_node, pattern_name: str, pattern_def: dict, 
                                    language: str, source_code: str) -> List[Dict[str, Any]]:
        """Process tree-sitter captures in a separate task."""
        patterns = []
        for capture in query.captures(root_node):
            capture_name, node = capture
            
            # Extract the pattern content using the block extractor
            block = self.block_extractor.extract_block(language, source_code, node)
            if block and block.content:
                # Create a mock capture result to pass to the extract function
                capture_result = {
                    'node': node,
                    'captures': {capture_name: node},
                    'text': block.content
                }
                
                # Apply the extract function to get metadata
                try:
                    metadata = pattern_def['extract'](capture_result)
                    
                    if metadata:
                        patterns.append({
                            'name': pattern_name,
                            'content': block.content,
                            'pattern_type': metadata.get('type', PatternType.CUSTOM),
                            'language': language,
                            'confidence': 0.95,  # Higher confidence with tree-sitter
                            'metadata': metadata
                        })
                except Exception as e:
                    log(f"Error in extract function for {pattern_name}: {str(e)}", level="error")
        return patterns
        
    @handle_async_errors(error_types=(Exception,))
    async def _extract_code_structure_patterns(self, source_code: str, language_rules: Dict[str, Any], language_id: str = None) -> List[Dict[str, Any]]:
        """Extract code structure patterns from source using regex or tree-sitter queries."""
        patterns = []
        
        async with AsyncErrorBoundary("extract_code_structure", error_types=(Exception,)):
            # Extract classes first
            class_pattern = language_rules.get('class_pattern')
            if class_pattern:
                future = submit_async_task(self._process_class_patterns(source_code, class_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    class_patterns = await asyncio.wrap_future(future)
                    patterns.extend(class_patterns)
                finally:
                    self._pending_tasks.remove(future)
            
            # Extract functions/methods
            function_pattern = language_rules.get('function_pattern')
            if function_pattern:
                future = submit_async_task(self._process_function_patterns(source_code, function_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    func_patterns = await asyncio.wrap_future(future)
                    patterns.extend(func_patterns)
                finally:
                    self._pending_tasks.remove(future)
        
        return patterns
    
    def _process_class_patterns(self, source_code: str, class_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process class patterns in a separate task."""
        patterns = []
        class_matches = re.finditer(class_pattern, source_code)
        for match in class_matches:
            class_name = match.group('class_name') if 'class_name' in match.groupdict() else ""
            class_start = match.start()
            
            # Use improved block extraction with language awareness
            class_content = self._extract_block_content(source_code, class_start, language_id)
            
            if class_content:
                patterns.append({
                    'name': f'class_{class_name}',
                    'content': class_content,
                    'pattern_type': PatternType.CLASS_DEFINITION,
                    'language': language_id or 'unknown',
                    'confidence': 0.9,
                    'metadata': {
                        'type': 'class',
                        'name': class_name
                    }
                })
        return patterns
        
    def _process_function_patterns(self, source_code: str, function_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process function patterns in a separate task."""
        patterns = []
        func_matches = re.finditer(function_pattern, source_code)
        for match in func_matches:
            func_name = match.group('func_name') if 'func_name' in match.groupdict() else ""
            func_start = match.start()
            
            # Use improved block extraction with language awareness
            func_content = self._extract_block_content(source_code, func_start, language_id)
            
            if func_content:
                patterns.append({
                    'name': f'function_{func_name}',
                    'content': func_content,
                    'pattern_type': PatternType.FUNCTION_DEFINITION,
                    'language': language_id or 'unknown',
                    'confidence': 0.85,
                    'metadata': {
                        'type': 'function',
                        'name': func_name
                    }
                })
        return patterns
    
    @handle_async_errors(error_types=(Exception,))
    async def _extract_naming_convention_patterns(self, source_code: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns."""
        patterns = []
        naming_conventions = language_rules.get('naming_conventions', {})
        
        # Extract variable naming patterns
        if 'variable' in naming_conventions:
            var_pattern = naming_conventions['variable']
            future = submit_async_task(self._process_variable_patterns(source_code, var_pattern, language_rules))
            self._pending_tasks.add(future)
            try:
                var_patterns = await asyncio.wrap_future(future)
                patterns.extend(var_patterns)
            finally:
                self._pending_tasks.remove(future)
        
        return patterns
        
    def _process_variable_patterns(self, source_code: str, var_pattern: str, language_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process variable patterns in a separate task."""
        patterns = []
        var_matches = re.finditer(r'(?<!def\s)(?<!class\s)(?<!import\s)(\b' + var_pattern + r')\s*=', source_code)
        
        var_names = set()
        for match in var_matches:
            var_name = match.group(1)
            if var_name not in var_names:
                var_names.add(var_name)
                patterns.append({
                    'name': f'variable_naming',
                    'content': var_name,
                    'language': language_rules.get('language', 'unknown'),
                    'confidence': 0.7,
                    'metadata': {
                        'type': 'naming_convention',
                        'subtype': 'variable'
                    }
                })
        return patterns
    
    @handle_async_errors(error_types=(Exception,))
    async def _extract_error_handling_patterns(self, source_code: str, language_rules: Dict[str, Any], language_id: str = None) -> List[Dict[str, Any]]:
        """Extract error handling patterns from source."""
        patterns = []
        
        async with AsyncErrorBoundary("extract_error_handling", error_types=(Exception,)):
            # Extract try/catch blocks
            try_pattern = language_rules.get('try_pattern')
            if try_pattern:
                future = submit_async_task(self._process_try_catch_patterns(source_code, try_pattern, language_id))
                self._pending_tasks.add(future)
                try:
                    try_patterns = await asyncio.wrap_future(future)
                    patterns.extend(try_patterns)
                finally:
                    self._pending_tasks.remove(future)
        
        return patterns
        
    def _process_try_catch_patterns(self, source_code: str, try_pattern: str, language_id: str) -> List[Dict[str, Any]]:
        """Process try/catch patterns in a separate task."""
        patterns = []
        try_matches = re.finditer(try_pattern, source_code)
        for match in try_matches:
            try_start = match.start()
            
            # Use improved block extraction with language awareness
            try_block = self._extract_block_content(source_code, try_start, language_id)
            
            if try_block:
                patterns.append({
                    'name': 'error_handling',
                    'content': try_block,
                    'pattern_type': PatternType.ERROR_HANDLING,
                    'language': language_id or 'unknown',
                    'confidence': 0.8,
                    'metadata': {
                        'type': 'try_catch',
                        'has_finally': 'finally' in try_block.lower(),
                        'has_multiple_catches': try_block.lower().count('catch') > 1
                    }
                })
        return patterns

    @handle_async_errors(error_types=(Exception,))
    async def _extract_block_content(self, source_code: str, start_pos: int, language_id: str = None) -> Optional[str]:
        """
        Extract a code block (like function/class body) starting from a position.
        Uses tree-sitter block extraction if available, otherwise falls back to heuristic approach.
        
        Args:
            source_code: The complete source code
            start_pos: Position where the block starts
            language_id: Optional language identifier for language-specific extraction
            
        Returns:
            Extracted block content or None if extraction failed
        """
        async with AsyncErrorBoundary("extract_block_content", error_types=(Exception,)):
            # If we have a language ID and it's supported by tree-sitter, use the block extractor
            if language_id and language_id in self.tree_sitter_languages:
                try:
                    # Use tree-sitter to parse the source and find the node at the position
                    from tree_sitter_language_pack import get_parser
                    parser = get_parser(language_id)
                    if parser:
                        # Parse the source code asynchronously
                        future = submit_async_task(parser.parse(source_code.encode("utf8")))
                        self._pending_tasks.add(future)
                        try:
                            tree = await asyncio.wrap_future(future)
                        finally:
                            self._pending_tasks.remove(future)
                        
                        if not tree:
                            return None
                        
                        # Find the block containing the starting position
                        # Convert start_pos to line and column
                        lines = source_code[:start_pos].splitlines()
                        if not lines:
                            line = 0
                            col = start_pos
                        else:
                            line = len(lines) - 1
                            col = len(lines[-1])
                        
                        # Get the node at the position
                        cursor = tree.root_node.walk()
                        cursor.goto_first_child_for_point((line, col))
                        
                        # Try to extract the block
                        if cursor.node:
                            # Extract block asynchronously
                            future = submit_async_task(self.block_extractor.extract_block(language_id, source_code, cursor.node))
                            self._pending_tasks.add(future)
                            try:
                                block = await asyncio.wrap_future(future)
                                if block and block.content:
                                    return block.content
                            finally:
                                self._pending_tasks.remove(future)
                except Exception as e:
                    log(f"Tree-sitter block extraction failed, falling back to heuristic: {str(e)}", level="debug")
            
            # Fallback to the heuristic approach
            # Submit the heuristic extraction as a task to avoid blocking
            future = submit_async_task(self._extract_block_heuristic(source_code, start_pos))
            self._pending_tasks.add(future)
            try:
                return await asyncio.wrap_future(future)
            finally:
                self._pending_tasks.remove(future)
        
        return None

    def _extract_block_heuristic(self, source_code: str, start_pos: int) -> Optional[str]:
        """Helper method to extract block content using heuristic approach in a separate task."""
        # Find the opening brace or colon
        block_start = source_code.find(':', start_pos)
        if block_start == -1:
            block_start = source_code.find('{', start_pos)
            if block_start == -1:
                return None
                
        # Simple approach to find block end - this is a heuristic
        # and would be better with actual parsing
        lines = source_code[block_start:].splitlines()
        
        if not lines:
            return None
            
        # Handle Python indentation-based blocks
        if source_code[block_start] == ':':
            block_content = [lines[0]]
            initial_indent = len(lines[1]) - len(lines[1].lstrip()) if len(lines) > 1 else 0
            
            for i, line in enumerate(lines[1:], 1):
                if line.strip() and len(line) - len(line.lstrip()) <= initial_indent:
                    break
                block_content.append(line)
                
            return '\n'.join(block_content)
        
        # Handle brace-based blocks
        else:
            brace_count = 1
            block_content = [lines[0]]
            
            for i, line in enumerate(lines[1:], 1):
                block_content.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count <= 0:
                    break
                    
            return '\n'.join(block_content)

    async def cleanup(self):
        """Clean up pattern processor resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear pattern caches
            self._tree_sitter_patterns.clear()
            self._regex_patterns.clear()
            self._loaded_languages.clear()
            
            self._initialized = False
            log("Pattern processor cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up pattern processor: {e}", level="error")

# Global instance
pattern_processor = PatternProcessor() 