"""[4.0] Tree-sitter based parsing implementation."""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
from dataclasses import dataclass, field
from tree_sitter import Language, Parser, Tree, Node
from parsers.types import (
    FileType, ParserType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel
)
from parsers.models import (
    FileClassification, ParserResult, BaseNodeDict,
    TreeSitterNodeDict
)
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.language_mapping import (
    TREE_SITTER_LANGUAGES,
    get_parser_type,
    get_file_type,
    get_ai_capabilities
)
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator

@dataclass
class TreeSitterParser(BaseParserInterface, AIParserInterface):
    """[4.1] Tree-sitter parser implementation with AI capabilities."""
    
    def __init__(self, language_id: str):
        """Initialize tree-sitter parser."""
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.TREE_SITTER,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._parser = None
        self._language = None
        self._cache = None
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the parser is initialized."""
        if not self._initialized:
            raise ProcessingError(f"Tree-sitter parser not initialized for {self.language_id}. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, language_id: str) -> 'TreeSitterParser':
        """[4.1.1] Create and initialize a tree-sitter parser instance."""
        instance = cls(language_id)
        try:
            async with AsyncErrorBoundary(f"tree_sitter_parser_initialization_{language_id}"):
                # Initialize parser
                instance._parser = Parser()
                instance._language = await Language.load(language_id)
                instance._parser.set_language(instance._language)
                
                # Initialize cache
                instance._cache = UnifiedCache(f"tree_sitter_{language_id}")
                await cache_coordinator.register_cache(instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                log(f"Tree-sitter parser initialized for {language_id}", level="info")
                return instance
        except Exception as e:
            log(f"Error initializing tree-sitter parser for {language_id}: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize tree-sitter parser for {language_id}: {e}")
    
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """[4.1.2] Parse source code using tree-sitter."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"tree_sitter_parse_{self.language_id}"):
            try:
                # Check cache first
                cache_key = f"ast:{hash(source_code)}"
                cached_result = await self._cache.get(cache_key)
                if cached_result:
                    return ParserResult(**cached_result)
                
                # Parse source code
                tree = self._parser.parse(bytes(source_code, "utf8"))
                if not tree:
                    return None
                
                # Convert tree to dictionary format
                ast = await self._tree_to_dict(tree)
                
                # Extract features
                features = await self._extract_features(tree.root_node, source_code)
                
                # Create result
                result = ParserResult(
                    success=True,
                    ast=ast,
                    features=features.features,
                    documentation=features.documentation.__dict__,
                    complexity=features.metrics.__dict__,
                    statistics=self.stats.__dict__,
                    errors=[]
                )
                
                # Cache result
                await self._cache.set(cache_key, result.__dict__)
                
                return result
            except Exception as e:
                log(f"Error parsing {self.language_id} code: {e}", level="error")
                return None
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[4.1.3] Process source code with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"tree_sitter_ai_processing_{self.language_id}"):
            try:
                results = AIProcessingResult(success=True)
                
                # Parse source code first
                parse_result = await self.parse(source_code)
                if not parse_result or not parse_result.success:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse source code"
                    )
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(parse_result, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(parse_result, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(parse_result, context)
                    results.ai_insights.update(modification)
                
                # Process with review capability
                if AICapability.CODE_REVIEW in self.capabilities:
                    review = await self._process_with_review(parse_result, context)
                    results.ai_insights.update(review)
                
                # Process with learning capability
                if AICapability.LEARNING in self.capabilities:
                    learning = await self._process_with_learning(parse_result, context)
                    results.learned_patterns.extend(learning)
                
                return results
            except Exception as e:
                log(f"Error in tree-sitter AI processing for {self.language_id}: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _process_with_understanding(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[4.1.4] Process with code understanding capability."""
        understanding = {}
        
        # Analyze AST structure
        if parse_result.ast:
            understanding["structure"] = await self._analyze_ast_structure(parse_result.ast)
        
        # Analyze semantic information
        if parse_result.features:
            understanding["semantics"] = await self._analyze_semantics(parse_result.features)
        
        # Add documentation insights
        if parse_result.documentation:
            understanding["documentation"] = parse_result.documentation
        
        return understanding
    
    async def _process_with_generation(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> List[str]:
        """[4.1.5] Process with code generation capability."""
        suggestions = []
        
        # Generate completion suggestions
        if parse_result.ast:
            completions = await self._generate_completions(parse_result.ast, context)
            suggestions.extend(completions)
        
        # Generate improvement suggestions
        if parse_result.features:
            improvements = await self._generate_improvements(parse_result.features, context)
            suggestions.extend(improvements)
        
        return suggestions
    
    async def _process_with_modification(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[4.1.6] Process with code modification capability."""
        insights = {}
        
        # Analyze modification impact
        if parse_result.ast:
            insights["impact"] = await self._analyze_modification_impact(parse_result.ast, context)
        
        # Generate modification suggestions
        if parse_result.features:
            insights["suggestions"] = await self._generate_modification_suggestions(
                parse_result.features,
                context
            )
        
        return insights
    
    async def _process_with_review(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> Dict[str, Any]:
        """[4.1.7] Process with code review capability."""
        return {
            "quality": await self._assess_code_quality(parse_result),
            "issues": await self._identify_code_issues(parse_result),
            "suggestions": await self._generate_review_suggestions(parse_result, context)
        }
    
    async def _process_with_learning(
        self,
        parse_result: ParserResult,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """[4.1.8] Process with learning capability."""
        patterns = []
        
        # Learn from code structure
        if parse_result.ast:
            structure_patterns = await self._learn_structure_patterns(parse_result.ast)
            patterns.extend(structure_patterns)
        
        # Learn from features
        if parse_result.features:
            feature_patterns = await self._learn_feature_patterns(parse_result.features)
            patterns.extend(feature_patterns)
        
        return patterns
    
    async def _tree_to_dict(self, tree: Tree) -> Dict[str, Any]:
        """[4.1.9] Convert tree-sitter tree to dictionary format."""
        return {
            "root": await self._node_to_dict(tree.root_node),
            "metadata": {
                "language": self.language_id,
                "parser_type": self.parser_type.value
            }
        }
    
    async def _node_to_dict(self, node: Node) -> TreeSitterNodeDict:
        """[4.1.10] Convert tree-sitter node to dictionary format."""
        return {
            "type": node.type,
            "start_point": list(node.start_point),
            "end_point": list(node.end_point),
            "children": [await self._node_to_dict(child) for child in node.children],
            "metadata": {
                "is_named": node.is_named,
                "has_error": node.has_error,
                "grammar_name": node.grammar_name
            }
        }
    
    async def cleanup(self):
        """[4.1.11] Clean up parser resources."""
        try:
            if not self._initialized:
                return
                
            # Clear parser and language
            self._parser = None
            self._language = None
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
                self._cache = None
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log(f"Tree-sitter parser cleaned up for {self.language_id}", level="info")
        except Exception as e:
            log(f"Error cleaning up tree-sitter parser for {self.language_id}: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup tree-sitter parser for {self.language_id}: {e}")

# Global instance cache
_parser_instances: Dict[str, TreeSitterParser] = {}

async def get_tree_sitter_parser(language_id: str) -> Optional[TreeSitterParser]:
    """[4.2] Get a tree-sitter parser instance for a language."""
    if language_id not in _parser_instances:
        try:
            parser = await TreeSitterParser.create(language_id)
            _parser_instances[language_id] = parser
        except Exception as e:
            log(f"Error creating tree-sitter parser for {language_id}: {e}", level="error")
            return None
    
    return _parser_instances[language_id] 