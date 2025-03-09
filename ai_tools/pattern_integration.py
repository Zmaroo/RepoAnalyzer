"""Integration layer between pattern processing and AI tools.

This module provides integration between pattern processing and AI tools,
supporting both custom parsers and tree-sitter parsers through tree-sitter-language-pack.

Flow:
1. Pattern Processing:
   - Custom parser patterns (highest precedence)
   - Tree-sitter patterns (via language-pack)
   - Fallback patterns

2. Integration Points:
   - Pattern Processor: Core pattern matching
   - AI Pattern Processor: AI-enhanced patterns
   - Tree-sitter Language Pack: Standard language support
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import asyncio
from dataclasses import dataclass
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    PatternCategory, PatternPurpose, FileType,
    InteractionType, ConfidenceLevel,
    AIContext, AIProcessingResult,
    AICapability,
    get_purpose_from_interaction,
    get_categories_from_interaction,
    ParserType
)
from parsers.pattern_processor import PatternProcessor, ProcessedPattern
from parsers.ai_pattern_processor import AIPatternProcessor
from parsers.models import AIPatternResult
from .ai_interface import AIInterface
from .code_understanding import CodeUnderstanding
from .graph_capabilities import GraphCapabilities
from .reference_repository_learning import reference_learning
from .rule_config import RuleConfig
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from db.pattern_storage import pattern_storage
from db.transaction import transaction_scope

@dataclass
class PatternLearningMetrics:
    """Metrics for pattern learning operations."""
    total_patterns_learned: int = 0
    code_patterns_learned: int = 0
    doc_patterns_learned: int = 0
    arch_patterns_learned: int = 0
    cross_repo_patterns: int = 0
    last_update: float = 0.0
    tree_sitter_patterns: int = 0  # Track tree-sitter patterns
    custom_patterns: int = 0  # Track custom patterns

class PatternIntegration:
    """Integrates pattern processing with AI tools."""
    
    def __init__(self):
        """Initialize pattern integration."""
        self.ai_interface = None
        self.code_understanding = None
        self.graph_capabilities = None
        self.rule_config = None
        self._pattern_storage = None
        self._pattern_processor = None
        self._ai_processor = None
        self._initialized = False
        self._metrics = PatternLearningMetrics()
        self._tree_sitter_parsers = {}  # Cache for tree-sitter parsers
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
    
    @classmethod
    async def create(cls) -> 'PatternIntegration':
        """Create and initialize a PatternIntegration instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="pattern integration initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize components
                instance.ai_interface = await AIInterface.create()
                instance.code_understanding = await CodeUnderstanding.create()
                instance.graph_capabilities = await GraphCapabilities.create()
                instance.rule_config = RuleConfig()
                instance._pattern_storage = await pattern_storage.create()
                
                # Initialize pattern processors
                instance._pattern_processor = await PatternProcessor.create()
                instance._ai_processor = AIPatternProcessor(instance._pattern_processor)
                await instance._ai_processor.initialize()
                
                # Initialize tree-sitter parsers for supported languages
                await instance._initialize_tree_sitter_parsers()
                
                instance._initialized = True
                await log("Pattern integration initialized", level="info")
                
                return instance
        except Exception as e:
            await log(f"Error initializing pattern integration: {e}", level="error")
            raise

    async def _initialize_tree_sitter_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        try:
            for lang in SupportedLanguage.__args__:
                try:
                    parser = get_parser(lang)
                    if parser:
                        self._tree_sitter_parsers[lang] = parser
                except Exception as e:
                    await log(f"Error initializing tree-sitter parser for {lang}: {e}", level="warning")
        except Exception as e:
            await log(f"Error initializing tree-sitter parsers: {e}", level="error")

    async def process_interaction(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process an interaction using all available tools."""
        if not self._initialized:
            await self.create()

        try:
            async with AsyncErrorBoundary("pattern_integration_processing"):
                # Start coordinated transaction
                async with transaction_scope() as txn:
                    # Get pattern storage instance
                    storage = await pattern_storage.get_pattern_storage()
                    
                    # Determine parser type based on language
                    parser_type = await self._get_parser_type(context.language_id)
                    
                    # Check for cross-project learning opportunity
                    if context.repository_id and AICapability.LEARNING in context.capabilities:
                        # Get related repositories
                        related_repos = await self._get_related_repositories(context.repository_id)
                        if related_repos:
                            # Learn from related repositories
                            learning_results = await self._learn_from_repositories(
                                related_repos,
                                context.repository_id,
                                context
                            )
                            context.metadata["learning_results"] = learning_results
                    
                    # Process with core pattern processor first
                    base_patterns = await self._pattern_processor.process_for_purpose(
                        source_code,
                        get_purpose_from_interaction(context.interaction_type),
                        context.file_type,
                        get_categories_from_interaction(context.interaction_type),
                        parser_type=parser_type
                    )

                    # Create embeddings for patterns
                    for pattern in base_patterns:
                        try:
                            embedding = await self.embedder.embed_with_retry(pattern.content)
                            pattern.embedding = embedding.tolist() if hasattr(embedding, 'tolist') else None
                        except Exception as e:
                            await log(f"Error creating embedding: {e}", level="warning")
                            pattern.embedding = None

                    # Enhance with AI capabilities
                    ai_results = await self._ai_processor.process_with_ai(source_code, context)

                    # Store patterns and relationships
                    if ai_results.learned_patterns:
                        await storage.store_patterns(
                            context.repository_id,
                            {
                                "code": [p for p in ai_results.learned_patterns if p.category == PatternCategory.CODE_PATTERNS],
                                "doc": [p for p in ai_results.learned_patterns if p.category == PatternCategory.DOCUMENTATION],
                                "arch": [p for p in ai_results.learned_patterns if p.category == PatternCategory.ARCHITECTURE]
                            }
                        )

                    # Integrate results with other tools
                    integrated_results = await self._integrate_results(
                        base_patterns,
                        ai_results,
                        context,
                        parser_type
                    )

                    # Update metrics
                    self._update_metrics(integrated_results, parser_type)

                    return integrated_results

        except Exception as e:
            await log(f"Error in pattern integration: {e}", level="error")
            return AIProcessingResult(
                success=False,
                response=f"Error in pattern integration: {str(e)}"
            )

    async def _learn_from_repositories(
        self,
        source_repos: List[int],
        target_repo: int,
        context: AIContext
    ) -> Dict[str, Any]:
        """Learn patterns from related repositories."""
        try:
            # Get pattern storage
            storage = await pattern_storage.get_pattern_storage()
            
            # Get patterns from source repositories
            source_patterns = {}
            for repo_id in source_repos:
                patterns = await storage.get_patterns(repo_id)
                if patterns:
                    source_patterns[repo_id] = patterns
            
            # Analyze compatibility
            compatibility = await self._analyze_repo_compatibility(
                source_patterns,
                target_repo,
                context
            )
            
            # Transfer compatible patterns
            transfer_results = await self._transfer_compatible_patterns(
                source_patterns,
                compatibility,
                target_repo,
                context
            )
            
            return {
                "source_repos": len(source_repos),
                "patterns_analyzed": sum(len(p) for p in source_patterns.values()),
                "patterns_transferred": transfer_results["transferred"],
                "compatibility_scores": compatibility
            }
            
        except Exception as e:
            await log(f"Error learning from repositories: {e}", level="error")
            return {
                "error": str(e),
                "source_repos": len(source_repos),
                "patterns_analyzed": 0,
                "patterns_transferred": 0
            }

    async def _analyze_repo_compatibility(
        self,
        source_patterns: Dict[int, Dict[str, List[Dict[str, Any]]]],
        target_repo: int,
        context: AIContext
    ) -> Dict[int, float]:
        """Analyze compatibility between repositories."""
        compatibility = {}
        
        try:
            # Get target repo characteristics
            target_chars = await self._get_repo_characteristics(target_repo)
            
            for repo_id, patterns in source_patterns.items():
                # Get source repo characteristics
                source_chars = await self._get_repo_characteristics(repo_id)
                
                # Calculate compatibility scores
                language_match = self._calculate_language_compatibility(
                    source_chars["languages"],
                    target_chars["languages"]
                )
                
                pattern_match = self._calculate_pattern_compatibility(
                    patterns,
                    target_chars["patterns"]
                )
                
                # Weighted compatibility score
                compatibility[repo_id] = (
                    language_match * 0.6 +
                    pattern_match * 0.4
                )
            
            return compatibility
            
        except Exception as e:
            await log(f"Error analyzing repo compatibility: {e}", level="error")
            return {}

    async def _transfer_compatible_patterns(
        self,
        source_patterns: Dict[int, Dict[str, List[Dict[str, Any]]]],
        compatibility: Dict[int, float],
        target_repo: int,
        context: AIContext
    ) -> Dict[str, Any]:
        """Transfer compatible patterns to target repository."""
        results = {
            "transferred": 0,
            "failed": 0,
            "by_category": {
                "code": 0,
                "doc": 0,
                "arch": 0
            }
        }
        
        try:
            storage = await pattern_storage.get_pattern_storage()
            
            for repo_id, patterns in source_patterns.items():
                if compatibility.get(repo_id, 0) < 0.3:  # Skip low compatibility
                    continue
                
                # Adapt and transfer patterns
                for category in ["code", "doc", "arch"]:
                    if category in patterns:
                        for pattern in patterns[category]:
                            try:
                                # Adapt pattern to target context
                                adapted = await self._adapt_pattern(
                                    pattern,
                                    target_repo,
                                    compatibility[repo_id],
                                    context
                                )
                                
                                if adapted:
                                    # Store adapted pattern
                                    await storage.store_patterns(
                                        target_repo,
                                        {category: [adapted]}
                                    )
                                    results["transferred"] += 1
                                    results["by_category"][category] += 1
                            except Exception as e:
                                await log(f"Error transferring pattern: {e}", level="warning")
                                results["failed"] += 1
            
            return results
            
        except Exception as e:
            await log(f"Error transferring patterns: {e}", level="error")
            return results

    async def _get_related_repositories(self, repo_id: int) -> List[int]:
        """Get related repositories based on similarity."""
        try:
            async with transaction_scope() as txn:
                # Get repositories with similar characteristics
                related = await txn.fetch("""
                    SELECT r.id, r.similarity
                    FROM repository_similarities s
                    JOIN repositories r ON r.id = s.related_repo_id
                    WHERE s.repo_id = $1
                    AND s.similarity > 0.3
                    ORDER BY s.similarity DESC
                    LIMIT 5
                """, repo_id)
                
                return [r["id"] for r in related]
        except Exception as e:
            await log(f"Error getting related repositories: {e}", level="error")
            return []

    async def _get_parser_type(self, language_id: str) -> ParserType:
        """Determine parser type based on language."""
        from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
        
        # Custom parsers take precedence
        if language_id in CUSTOM_PARSER_CLASSES:
            return ParserType.CUSTOM
        
        # Check tree-sitter support
        if language_id in SupportedLanguage.__args__:
            return ParserType.TREE_SITTER
        
        return ParserType.UNKNOWN

    async def _integrate_results(
        self,
        base_patterns: List[ProcessedPattern],
        ai_results: AIProcessingResult,
        context: AIContext,
        parser_type: ParserType
    ) -> AIProcessingResult:
        """Integrate results from all tools."""
        integrated_results = AIProcessingResult(
            success=True,
            response=None,
            suggestions=[],
            context_info={},
            confidence=0.0,
            learned_patterns=[],
            ai_insights={}
        )

        try:
            # Add code understanding insights
            if self.code_understanding and AICapability.CODE_UNDERSTANDING in context.capabilities:
                understanding = await self.code_understanding.analyze_patterns(
                    base_patterns,
                    parser_type=parser_type  # Pass parser type for proper analysis
                )
                integrated_results.context_info.update(understanding)

            # Add graph insights
            if self.graph_capabilities and AICapability.CODE_MODIFICATION in context.capabilities:
                graph_insights = await self.graph_capabilities.analyze_patterns(
                    base_patterns,
                    parser_type=parser_type  # Pass parser type for proper analysis
                )
                integrated_results.ai_insights.update({"graph_analysis": graph_insights})

            # Add AI insights
            integrated_results.ai_insights.update(ai_results.ai_insights)
            integrated_results.learned_patterns.extend(ai_results.learned_patterns)

            # Calculate final confidence
            integrated_results.confidence = self._calculate_integrated_confidence(
                base_patterns,
                ai_results,
                context,
                parser_type
            )

            return integrated_results

        except Exception as e:
            await log(f"Error integrating results: {e}", level="error")
            return ai_results  # Fallback to AI results if integration fails

    def _calculate_integrated_confidence(
        self,
        base_patterns: List[ProcessedPattern],
        ai_results: AIProcessingResult,
        context: AIContext,
        parser_type: ParserType
    ) -> float:
        """Calculate confidence score for integrated results."""
        weights = {
            "base_patterns": 0.3,
            "ai_results": 0.4,
            "understanding": 0.2,
            "graph": 0.1
        }

        # Adjust weights based on parser type
        if parser_type == ParserType.CUSTOM:
            weights["base_patterns"] = 0.35  # Higher weight for custom parsers
            weights["ai_results"] = 0.35
        elif parser_type == ParserType.TREE_SITTER:
            weights["base_patterns"] = 0.3
            weights["ai_results"] = 0.4  # Higher weight for AI results with tree-sitter

        confidence = 0.0
        
        # Base pattern confidence
        if base_patterns:
            base_confidence = sum(p.confidence for p in base_patterns if hasattr(p, 'confidence')) / len(base_patterns)
            confidence += base_confidence * weights["base_patterns"]

        # AI results confidence
        confidence += ai_results.confidence * weights["ai_results"]

        # Understanding confidence
        if self.code_understanding and context.capabilities:
            understanding_confidence = self.code_understanding.get_confidence()
            confidence += understanding_confidence * weights["understanding"]

        # Graph confidence
        if self.graph_capabilities and context.capabilities:
            graph_confidence = self.graph_capabilities.get_confidence()
            confidence += graph_confidence * weights["graph"]

        return min(confidence, 1.0)

    def _update_metrics(self, results: AIProcessingResult, parser_type: ParserType):
        """Update metrics based on results and parser type."""
        self._metrics.total_patterns_learned += len(results.learned_patterns)
        
        if parser_type == ParserType.CUSTOM:
            self._metrics.custom_patterns += len(results.learned_patterns)
        elif parser_type == ParserType.TREE_SITTER:
            self._metrics.tree_sitter_patterns += len(results.learned_patterns)
        
        # Update other metrics
        for pattern in results.learned_patterns:
            if pattern.category == PatternCategory.CODE_PATTERNS:
                self._metrics.code_patterns_learned += 1
            elif pattern.category == PatternCategory.DOCUMENTATION:
                self._metrics.doc_patterns_learned += 1
            elif pattern.category == PatternCategory.ARCHITECTURE:
                self._metrics.arch_patterns_learned += 1

    async def cleanup(self):
        """Clean up integration resources."""
        try:
            if self._pattern_processor:
                await self._pattern_processor.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            if self.code_understanding:
                await self.code_understanding.cleanup()
            if self.graph_capabilities:
                await self.graph_capabilities.cleanup()
            
            # Clean up tree-sitter parsers
            self._tree_sitter_parsers.clear()
            
            # Cancel pending tasks
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._pending_tasks.clear()
            
            self._initialized = False
            await log("Pattern integration cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern integration: {e}", level="error")

    def get_metrics(self) -> PatternLearningMetrics:
        """Get integration metrics."""
        return self._metrics

# Global instance
pattern_integration = None

async def get_pattern_integration() -> PatternIntegration:
    """Get the global pattern integration instance."""
    global pattern_integration
    if pattern_integration is None:
        pattern_integration = await PatternIntegration.create()
    return pattern_integration 