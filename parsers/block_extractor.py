"""Tree-sitter based code block extraction.

This module provides utilities for extracting code blocks (like function bodies,
class definitions, etc.) from source code using tree-sitter's AST capabilities
rather than heuristic-based approaches.
"""

from typing import Dict, List, Optional, Any, Tuple, Set
import re
import asyncio
from dataclasses import dataclass
import time

from utils.logger import log
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorSeverity,
    ProcessingError
)
from tree_sitter_language_pack import get_parser, get_language
from parsers.types import (
    FileType, ParserType,
    AICapability, AIContext, AIProcessingResult
)
from parsers.models import PatternMatch
from parsers.parser_interfaces import AIParserInterface
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor
from utils.cache import cache_coordinator, UnifiedCache

@dataclass
class ExtractedBlock:
    """Represents an extracted code block with metadata."""
    content: str
    start_point: Tuple[int, int]
    end_point: Tuple[int, int]
    node_type: str
    metadata: Dict[str, Any] = None
    confidence: float = 1.0


class TreeSitterBlockExtractor(AIParserInterface):
    """Extracts code blocks from tree-sitter ASTs."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__(
            language_id="block_extractor",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_MODIFICATION
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._language_parsers: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._cache = None
        self._component_states = {
            'tree_sitter': False
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("Block extractor not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'TreeSitterBlockExtractor':
        """Async factory method to create and initialize a TreeSitterBlockExtractor instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="block extractor initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize cache
                instance._cache = UnifiedCache("block_extractor")
                await cache_coordinator.register_cache(instance._cache)
                
                # Initialize required components
                from tree_sitter import Language, Parser
                
                # Initialize parsers for supported languages
                supported_languages = ['python', 'javascript', 'typescript', 'java', 'cpp']
                for lang in supported_languages:
                    try:
                        task = asyncio.create_task(cls._init_language_parser(lang))
                        instance._pending_tasks.add(task)
                        try:
                            parser = await task
                            instance._language_parsers[lang] = parser
                        finally:
                            instance._pending_tasks.remove(task)
                    except Exception as e:
                        await log(f"Warning: Failed to initialize tree-sitter for {lang}: {e}", level="warning")
                
                if not instance._language_parsers:
                    raise ProcessingError("Failed to initialize any language parsers")
                
                instance._component_states['tree_sitter'] = True
                
                # Initialize AI capabilities
                if AICapability.CODE_UNDERSTANDING in instance.capabilities:
                    await instance._initialize_ai_understanding()
                if AICapability.CODE_MODIFICATION in instance.capabilities:
                    await instance._initialize_ai_modification()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component("block_extractor")
                
                instance._initialized = True
                await log("Block extractor initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing block extractor: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize block extractor: {e}")
    
    @staticmethod
    async def _init_language_parser(lang: str) -> Any:
        """Initialize a language parser."""
        try:
            from tree_sitter import Language, Parser
            return Language.build_library(
                f"build/{lang}.so",
                [f"vendor/tree-sitter-{lang}"]
            )
        except Exception as e:
            raise ProcessingError(f"Failed to initialize parser for {lang}: {e}")
    
    @handle_async_errors(error_types=(ProcessingError,))
    async def extract_block(self, 
                         language_id: str, 
                         source_code: str, 
                         node_or_match: Any) -> Optional[ExtractedBlock]:
        """
        Extract a code block from the given node or pattern match.
        
        Args:
            language_id: The language identifier
            source_code: The complete source code
            node_or_match: Either a tree-sitter Node or a PatternMatch
            
        Returns:
            An ExtractedBlock object or None if extraction fails
        """
        if not self._initialized:
            await self.ensure_initialized()
        
        async with self._lock:
            # Cache only the final extracted block result
            cache_key = f"block_{language_id}_{hash(source_code)}_{hash(str(node_or_match))}"
            if self._cache:
                cached_block = await self._cache.get(cache_key)
                if cached_block:
                    return ExtractedBlock(**cached_block)
            
            async with AsyncErrorBoundary(f"extracting block for {language_id}"):
                # If we were passed a PatternMatch, extract from the node
                if isinstance(node_or_match, PatternMatch):
                    node = node_or_match.node
                    if node is None:
                        # Try heuristic fallback for regex-based matches
                        result = await self._extract_block_heuristic(source_code, node_or_match)
                    else:
                        result = await self._extract_from_node(language_id, source_code, node)
                else:
                    # If we were passed a node directly
                    try:
                        result = await self._extract_from_node(language_id, source_code, node_or_match)
                    except Exception as e:
                        await log(f"Error extracting from node: {e}", level="warning")
                        # Try heuristic fallback
                        result = await self._extract_block_heuristic(source_code, node_or_match)
                
                # Cache only the final extracted block result
                if self._cache and result:
                    await self._cache.set(cache_key, {
                        'content': result.content,
                        'start_point': result.start_point,
                        'end_point': result.end_point,
                        'node_type': result.node_type,
                        'metadata': result.metadata,
                        'confidence': result.confidence
                    })
                
                return result

    async def _extract_block_heuristic(self, source_code: str, node_or_match: Any) -> Optional[ExtractedBlock]:
        """
        Fallback method that uses heuristics to extract a block when tree-sitter isn't available.
        
        Args:
            source_code: The source code
            node_or_match: A PatternMatch or node-like object with position information
            
        Returns:
            An ExtractedBlock with the extracted content
        """
        try:
            # For PatternMatch objects
            if isinstance(node_or_match, PatternMatch):
                start_line = node_or_match.line
                start_col = node_or_match.column
                raw_snippet = node_or_match.snippet
                
                # Find the context around the match
                lines = source_code.split('\n')
                
                # Simple heuristic: extract the matched line and a few lines after
                # More sophisticated heuristics could be implemented
                context_lines = []
                
                # Include the matched line
                if 0 <= start_line < len(lines):
                    context_lines.append(lines[start_line])
                    
                    # Try to extract a few more lines to include the block
                    # This is a simple heuristic and might be improved
                    line_index = start_line + 1
                    while line_index < len(lines) and line_index < start_line + 10:
                        context_lines.append(lines[line_index])
                        line_index += 1
                        
                        # Stop if we encounter a line with reduced indentation
                        if line_index < len(lines) and lines[line_index].strip() and \
                           len(lines[line_index]) - len(lines[line_index].lstrip()) < \
                           len(lines[start_line]) - len(lines[start_line].lstrip()):
                            break
                
                extracted_content = '\n'.join(context_lines)
                
                return ExtractedBlock(
                    content=extracted_content,
                    start_point=(start_line, start_col),
                    end_point=(start_line + len(context_lines) - 1, len(context_lines[-1])),
                    node_type="heuristic_block",
                    metadata={"source": "heuristic"},
                    confidence=0.6  # Lower confidence for heuristic extraction
                )
            
            # For node-like objects, try to extract position information
            else:
                # This assumes the node has start_point and end_point attributes
                try:
                    start_point = (node_or_match.start_point[0], node_or_match.start_point[1])
                    end_point = (node_or_match.end_point[0], node_or_match.end_point[1])
                    
                    # Extract the content from the source code based on these positions
                    lines = source_code.split('\n')
                    content_lines = lines[start_point[0]:end_point[0] + 1]
                    
                    # Adjust first and last line based on column positions
                    if len(content_lines) > 0:
                        content_lines[0] = content_lines[0][start_point[1]:]
                        if len(content_lines) > 1:
                            content_lines[-1] = content_lines[-1][:end_point[1]]
                    
                    content = '\n'.join(content_lines)
                    
                    return ExtractedBlock(
                        content=content,
                        start_point=start_point,
                        end_point=end_point,
                        node_type="heuristic_block",
                        metadata={"source": "heuristic"},
                        confidence=0.7  # Medium confidence for node-based heuristic
                    )
                except AttributeError:
                    # If the node doesn't have the expected attributes
                    return None
        
        except Exception as e:
            log(f"Heuristic extraction failed: {e}", level="warning")
            return None
    
    async def _extract_from_node(self, language_id: str, source_code: str, node: Any) -> Optional[ExtractedBlock]:
        """Extract a code block from a tree-sitter Node."""
        if not node:
            return None
            
        try:
            # Get the text content directly from the node if possible
            if hasattr(node, 'text') and callable(getattr(node, 'text', None)):
                # For tree-sitter Node objects
                text = node.text.decode('utf8')
                
                # For some languages, we may need special handling based on node type
                if language_id == 'python' and node.type in ('function_definition', 'class_definition'):
                    # For Python definitions, we want to include the entire block
                    # Look for the body child for more precise extraction
                    body_node = None
                    for child in node.children:
                        if child.type == 'block' or (hasattr(child, 'field') and child.field == 'body'):
                            body_node = child
                            break
                    
                    if body_node:
                        # Use the body node instead
                        text = body_node.text.decode('utf8')
                        node = body_node
                
                return ExtractedBlock(
                    content=text,
                    start_point=node.start_point,
                    end_point=node.end_point,
                    node_type=node.type,
                    metadata={'direct': True}
                )
            
            # Fallback if we can't get text directly
            start_byte = node.start_byte if hasattr(node, 'start_byte') else None
            end_byte = node.end_byte if hasattr(node, 'end_byte') else None
            
            if start_byte is not None and end_byte is not None:
                # Extract using byte positions
                content = source_code[start_byte:end_byte]
                return ExtractedBlock(
                    content=content,
                    start_point=node.start_point if hasattr(node, 'start_point') else (0, 0),
                    end_point=node.end_point if hasattr(node, 'end_point') else (0, 0),
                    node_type=node.type if hasattr(node, 'type') else 'unknown',
                    metadata={'byte_extraction': True}
                )
        
        except Exception as e:
            log(f"Error extracting block content: {str(e)}", level="error")
        
        return None

    async def get_child_blocks(self, language_id: str, source_code: str, parent_node: Any) -> List[ExtractedBlock]:
        """
        Extract all child blocks from a parent node.
        
        Args:
            language_id: The language identifier
            source_code: The complete source code
            parent_node: The parent node to extract children from
            
        Returns:
            List of ExtractedBlock objects
        """
        if not self._initialized:
            await self.ensure_initialized()
            
        blocks = []
        
        async with AsyncErrorBoundary("get_child_blocks", error_types=(Exception,)):
            if not parent_node or not hasattr(parent_node, 'children'):
                return blocks
            
            for child in parent_node.children:
                # Only process named nodes (ignore syntax nodes like brackets)
                if not child.is_named:
                    continue
                    
                # Check if this is a block-like node based on type
                if await self._is_block_node(language_id, child):
                    task = asyncio.create_task(self._extract_from_node(language_id, source_code, child))
                    self._pending_tasks.add(task)
                    try:
                        block = await task
                        if block:
                            blocks.append(block)
                    finally:
                        self._pending_tasks.remove(task)
                
                # Recursively process child blocks for certain container nodes
                if await self._is_container_node(language_id, child):
                    task = asyncio.create_task(self.get_child_blocks(language_id, source_code, child))
                    self._pending_tasks.add(task)
                    try:
                        child_blocks = await task
                        blocks.extend(child_blocks)
                    finally:
                        self._pending_tasks.remove(task)
        
        return blocks
    
    async def _is_block_node(self, language_id: str, node: Any) -> bool:
        """Determine if a node represents a code block based on language-specific rules."""
        if not hasattr(node, 'type'):
            return False
            
        # Common block node types across languages
        common_block_types = {
            'block', 'compound_statement', 'statement_block',
            'function_body', 'class_body', 'method_body'
        }
        
        # Language-specific block types
        language_block_types = {
            'python': {'block', 'function_definition', 'class_definition', 'if_statement',
                      'for_statement', 'while_statement', 'try_statement'},
            'javascript': {'statement_block', 'function_declaration', 'method_definition',
                          'class_declaration', 'if_statement', 'for_statement'},
            'typescript': {'statement_block', 'function_declaration', 'method_definition',
                          'class_declaration', 'interface_declaration'},
            'cpp': {'compound_statement', 'function_definition', 'class_specifier',
                   'namespace_definition', 'if_statement', 'for_statement'},
            'java': {'block', 'class_body', 'method_declaration', 'constructor_declaration',
                    'if_statement', 'for_statement', 'try_statement'},
            'go': {'block', 'function_declaration', 'method_declaration', 
                  'if_statement', 'for_statement'},
            'rust': {'block', 'function_item', 'impl_item', 'for_expression', 'if_expression'}
        }
        
        # Check common types first
        if node.type in common_block_types:
            return True
            
        # Check language-specific types
        if language_id in language_block_types and node.type in language_block_types[language_id]:
            return True
            
        return False
    
    async def _is_container_node(self, language_id: str, node: Any) -> bool:
        """
        Determine if a node is a container that might have block children.
        This helps with recursive traversal of the AST.
        """
        if not hasattr(node, 'type'):
            return False
            
        # Common container node types across languages
        common_container_types = {
            'program', 'source_file', 'translation_unit',
            'namespace', 'module', 'package'
        }
        
        # Language-specific container types
        language_container_types = {
            'python': {'module', 'class_definition', 'function_definition'},
            'javascript': {'program', 'class_declaration', 'function_declaration', 'object'},
            'typescript': {'program', 'class_declaration', 'interface_declaration', 'namespace_declaration'},
            'cpp': {'translation_unit', 'namespace_definition', 'class_specifier'},
            'java': {'program', 'class_declaration', 'method_declaration'},
            'go': {'source_file', 'function_declaration', 'type_declaration'},
            'rust': {'source_file', 'impl_item', 'trait_item', 'mod_item'}
        }
        
        # Check common types first
        if node.type in common_container_types:
            return True
            
        # Check language-specific types
        if language_id in language_container_types and node.type in language_container_types[language_id]:
            return True
            
        return False

    async def cleanup(self):
        """Clean up block extractor resources."""
        try:
            if not self._initialized:
                return
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear parser cache
            if self._component_states['tree_sitter']:
                self._language_parsers.clear()
                self._component_states['tree_sitter'] = False
            
            # Cleanup cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("block_extractor")
            
            self._initialized = False
            await log("Block extractor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up block extractor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup block extractor: {e}")

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("block extractor AI processing"):
            try:
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(source_code, context)
                    results.context_info.update(understanding)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(source_code, context)
                    results.ai_insights.update(modification)
                
                return results
            except Exception as e:
                log(f"Error in block extractor AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _process_with_understanding(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code understanding capability."""
        understanding = {}
        
        # Extract blocks with context
        blocks = await self._extract_blocks_with_context(source_code, context)
        if blocks:
            understanding["blocks"] = blocks
        
        # Analyze block relationships
        relationships = await self._analyze_block_relationships(blocks)
        if relationships:
            understanding["relationships"] = relationships
        
        return understanding
    
    async def _process_with_modification(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code modification capability."""
        insights = {}
        
        # Analyze modification impact on blocks
        blocks = await self._extract_blocks_with_context(source_code, context)
        if blocks:
            insights["block_impact"] = await self._analyze_block_modifications(blocks, context)
        
        # Generate block-based suggestions
        suggestions = await self._generate_block_suggestions(blocks, context)
        if suggestions:
            insights["suggestions"] = suggestions
        
        return insights
    
    async def _extract_blocks_with_context(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Extract code blocks with contextual information."""
        blocks = []
        
        # Get the appropriate parser for the language
        language_id = context.project.language_id
        parser = self._language_parsers.get(language_id)
        if not parser:
            return blocks
        
        try:
            # Parse the source code
            tree = await parser.parse(source_code.encode("utf8"))
            if not tree:
                return blocks
            
            # Extract blocks from AST
            cursor = tree.walk()
            while cursor.goto_first_child():
                if await self._is_block_node(language_id, cursor.node):
                    block = await self.extract_block(language_id, source_code, cursor.node)
                    if block:
                        blocks.append({
                            "content": block.content,
                            "type": block.node_type,
                            "location": {
                                "start": block.start_point,
                                "end": block.end_point
                            },
                            "metadata": block.metadata or {}
                        })
                
                # Process siblings
                while cursor.goto_next_sibling():
                    if await self._is_block_node(language_id, cursor.node):
                        block = await self.extract_block(language_id, source_code, cursor.node)
                        if block:
                            blocks.append({
                                "content": block.content,
                                "type": block.node_type,
                                "location": {
                                    "start": block.start_point,
                                    "end": block.end_point
                                },
                                "metadata": block.metadata or {}
                            })
        except Exception as e:
            log(f"Error extracting blocks with context: {e}", level="error")
        
        return blocks
    
    async def _analyze_block_relationships(
        self,
        blocks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze relationships between code blocks."""
        relationships = {
            "containment": [],  # Blocks that contain other blocks
            "dependencies": [], # Blocks that depend on each other
            "sequence": []      # Blocks that form a sequence
        }
        
        for i, block1 in enumerate(blocks):
            for j, block2 in enumerate(blocks[i+1:], i+1):
                # Check containment
                if self._is_block_contained(block1, block2):
                    relationships["containment"].append({
                        "container": block1["type"],
                        "contained": block2["type"]
                    })
                
                # Check dependencies
                if self._have_dependency(block1, block2):
                    relationships["dependencies"].append({
                        "from": block1["type"],
                        "to": block2["type"]
                    })
                
                # Check sequence
                if self._are_sequential(block1, block2):
                    relationships["sequence"].append({
                        "first": block1["type"],
                        "second": block2["type"]
                    })
        
        return relationships
    
    async def _analyze_block_modifications(
        self,
        blocks: List[Dict[str, Any]],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze impact of modifications on blocks."""
        impact = {
            "affected_blocks": [],    # Blocks that would be affected
            "safety_assessment": {},  # Safety of modifying each block
            "complexity_change": {}   # How modifications affect complexity
        }
        
        for block in blocks:
            # Check if block would be affected
            if self._is_block_affected(block, context):
                impact["affected_blocks"].append(block["type"])
                
                # Assess modification safety
                impact["safety_assessment"][block["type"]] = self._assess_block_safety(block)
                
                # Estimate complexity change
                impact["complexity_change"][block["type"]] = self._estimate_complexity_change(block)
        
        return impact
    
    async def _generate_block_suggestions(
        self,
        blocks: List[Dict[str, Any]],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for block modifications."""
        suggestions = []
        
        for block in blocks:
            # Generate block-specific suggestions
            block_suggestions = self._get_block_suggestions(block, context)
            if block_suggestions:
                suggestions.append({
                    "block_type": block["type"],
                    "suggestions": block_suggestions
                })
        
        return suggestions
    
    def _is_block_contained(self, block1: Dict[str, Any], block2: Dict[str, Any]) -> bool:
        """Check if one block contains another."""
        start1 = block1["location"]["start"]
        end1 = block1["location"]["end"]
        start2 = block2["location"]["start"]
        end2 = block2["location"]["end"]
        
        return (start1[0] <= start2[0] and end1[0] >= end2[0] and
                (start1[0] < start2[0] or start1[1] <= start2[1]) and
                (end1[0] > end2[0] or end1[1] >= end2[1]))
    
    def _have_dependency(self, block1: Dict[str, Any], block2: Dict[str, Any]) -> bool:
        """Check if blocks have a dependency relationship."""
        # Simple check for variable usage
        return (block1["content"] in block2["content"] or
                block2["content"] in block1["content"])
    
    def _are_sequential(self, block1: Dict[str, Any], block2: Dict[str, Any]) -> bool:
        """Check if blocks form a logical sequence."""
        end1 = block1["location"]["end"]
        start2 = block2["location"]["start"]
        
        return (end1[0] < start2[0] or
                (end1[0] == start2[0] and end1[1] <= start2[1]))
    
    def _is_block_affected(self, block: Dict[str, Any], context: AIContext) -> bool:
        """Check if a block would be affected by modifications."""
        if not context.interaction.cursor_position:
            return False
            
        # Check if cursor is within block
        start = block["location"]["start"]
        end = block["location"]["end"]
        cursor = context.interaction.cursor_position
        
        return (start[0] <= cursor <= end[0])
    
    def _assess_block_safety(self, block: Dict[str, Any]) -> float:
        """Assess how safe it is to modify a block."""
        safety = 1.0
        
        # Reduce safety for complex blocks
        if len(block["content"].splitlines()) > 20:
            safety *= 0.8
        
        # Reduce safety for blocks with many dependencies
        if block.get("metadata", {}).get("dependencies", 0) > 5:
            safety *= 0.7
        
        return safety
    
    def _estimate_complexity_change(self, block: Dict[str, Any]) -> float:
        """Estimate how modifications would affect block complexity."""
        # Simple complexity metric based on lines and nesting
        current_complexity = len(block["content"].splitlines())
        current_complexity += block["content"].count("{") * 2
        
        # Estimate change (positive means increased complexity)
        return current_complexity * 0.2  # Assume 20% increase
    
    def _get_block_suggestions(
        self,
        block: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Get suggestions for block modifications."""
        suggestions = []
        
        # Suggest simplifying complex blocks
        if len(block["content"].splitlines()) > 20:
            suggestions.append("Consider breaking this block into smaller functions")
        
        # Suggest reducing dependencies
        if block.get("metadata", {}).get("dependencies", 0) > 5:
            suggestions.append("Consider reducing the number of dependencies")
        
        # Suggest following user's style
        if context.user.preferred_style:
            style_suggestions = self._check_style_compliance(block, context.user.preferred_style)
            suggestions.extend(style_suggestions)
        
        return suggestions
    
    def _check_style_compliance(
        self,
        block: Dict[str, Any],
        preferred_style: Dict[str, Any]
    ) -> List[str]:
        """Check if block follows preferred coding style."""
        suggestions = []
        
        # Check indentation
        if "indentation" in preferred_style:
            if not self._check_indentation(block["content"], preferred_style["indentation"]):
                suggestions.append(f"Use {preferred_style['indentation']} spaces for indentation")
        
        # Check naming conventions
        if "naming_convention" in preferred_style:
            if not self._check_naming(block["content"], preferred_style["naming_convention"]):
                suggestions.append("Follow the project's naming conventions")
        
        return suggestions
    
    def _check_indentation(self, content: str, preferred: int) -> bool:
        """Check if block uses preferred indentation."""
        lines = content.splitlines()
        for line in lines:
            if line.strip():
                spaces = len(line) - len(line.lstrip())
                if spaces % preferred != 0:
                    return False
        return True
    
    def _check_naming(self, content: str, convention: str) -> bool:
        """Check if block follows naming conventions."""
        # Simple check for common conventions
        if convention == "snake_case":
            return not re.search(r'[A-Z]', content)
        elif convention == "camelCase":
            return not re.search(r'_', content)
        return True

    async def analyze_cross_repository_patterns(
        self,
        repo_patterns: Dict[int, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze patterns across multiple repositories."""
        common_patterns = await self._find_common_patterns(repo_patterns)
        relationships = await self._analyze_pattern_relationships(common_patterns)
        return {
            "common_patterns": common_patterns,
            "relationships": relationships
        }

# Global instance
_block_extractor = None

async def get_block_extractor() -> TreeSitterBlockExtractor:
    """Get the global block extractor instance."""
    global _block_extractor
    if not _block_extractor:
        _block_extractor = await TreeSitterBlockExtractor.create()
    return _block_extractor 