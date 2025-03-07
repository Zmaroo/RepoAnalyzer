"""Integration layer between pattern processing and AI tools."""

from typing import Dict, Any, List, Optional, Set, Tuple
import asyncio
from dataclasses import dataclass
from parsers.types import (
    PatternCategory, PatternPurpose, FileType,
    InteractionType, ConfidenceLevel,
    AIContext, AIProcessingResult,
    AICapability,
    get_purpose_from_interaction,
    get_categories_from_interaction
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
                
                instance._initialized = True
                await log("Pattern integration initialized", level="info")
                
                return instance
        except Exception as e:
            await log(f"Error initializing pattern integration: {e}", level="error")
            raise

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
                    # Process with core pattern processor first
                    base_patterns = await self._pattern_processor.process_for_purpose(
                        source_code,
                        get_purpose_from_interaction(context.interaction.interaction_type),
                        context.project.file_type,
                        get_categories_from_interaction(context.interaction.interaction_type)
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

                    # Store patterns and relationships in Neo4j
                    if ai_results.learned_patterns:
                        await self.graph_capabilities.store_patterns(
                            ai_results.learned_patterns,
                            context.repository_id if context else None
                        )

                    # Integrate results with other tools
                    integrated_results = await self._integrate_results(
                        base_patterns,
                        ai_results,
                        context
                    )

                    # Update metrics
                    self._metrics.total_patterns_learned += len(integrated_results.learned_patterns)
                    self._metrics.code_patterns_learned += len([p for p in base_patterns if p.category == PatternCategory.CODE_PATTERNS])
                    self._metrics.doc_patterns_learned += len([p for p in base_patterns if p.category == PatternCategory.DOCUMENTATION])

                    return integrated_results

        except Exception as e:
            await log(f"Error in pattern integration: {e}", level="error")
            return AIProcessingResult(
                success=False,
                response=f"Error in pattern integration: {str(e)}"
            )

    async def _integrate_results(
        self,
        base_patterns: List[ProcessedPattern],
        ai_results: AIProcessingResult,
        context: AIContext
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
                understanding = await self.code_understanding.analyze_patterns(base_patterns)
                integrated_results.context_info.update(understanding)

            # Add graph insights
            if self.graph_capabilities and AICapability.CODE_MODIFICATION in context.capabilities:
                graph_insights = await self.graph_capabilities.analyze_patterns(base_patterns)
                integrated_results.ai_insights.update({"graph_analysis": graph_insights})

            # Add AI insights
            integrated_results.ai_insights.update(ai_results.ai_insights)
            integrated_results.learned_patterns.extend(ai_results.learned_patterns)

            # Update metrics
            self._metrics.total_patterns_learned += len(integrated_results.learned_patterns)
            self._metrics.code_patterns_learned += len([p for p in base_patterns if p.category == PatternCategory.CODE_PATTERNS])
            self._metrics.doc_patterns_learned += len([p for p in base_patterns if p.category == PatternCategory.DOCUMENTATION])

            # Calculate final confidence
            integrated_results.confidence = self._calculate_integrated_confidence(
                base_patterns,
                ai_results,
                context
            )

            return integrated_results

        except Exception as e:
            await log(f"Error integrating results: {e}", level="error")
            return ai_results  # Fallback to AI results if integration fails

    def _calculate_integrated_confidence(
        self,
        base_patterns: List[ProcessedPattern],
        ai_results: AIProcessingResult,
        context: AIContext
    ) -> float:
        """Calculate confidence score for integrated results."""
        weights = {
            "base_patterns": 0.3,
            "ai_results": 0.4,
            "understanding": 0.2,
            "graph": 0.1
        }

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