"""AI-specific pattern processing system."""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
from parsers.types import (
    PatternCategory, PatternPurpose, FileType,
    InteractionType, ConfidenceLevel,
    AIContext, AIProcessingResult,
    AICapability, AIConfidenceMetrics
)
from parsers.pattern_processor import PatternProcessor, ProcessedPattern
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.async_runner import submit_async_task
from embedding.embedding_models import code_embedder, doc_embedder, arch_embedder
from db.transaction import transaction_scope

class AIPatternProcessor(AIParserInterface):
    """AI-specific pattern processing system that extends the core pattern processor with AI capabilities."""
    
    def __init__(self, base_processor: PatternProcessor):
        """Initialize with base pattern processor."""
        super().__init__(
            language_id="ai_pattern_processor",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.DOCUMENTATION,
                AICapability.LEARNING,
                AICapability.DEEP_LEARNING
            }
        )
        self.base_processor = base_processor
        self._pattern_memory: Dict[str, float] = {}
        self._interaction_history: List[Dict[str, Any]] = []
        self._pattern_integration = None
        self._initialized = False
        self._embedders_initialized = False
        self._metrics = {
            "total_ai_processed": 0,
            "successful_ai_insights": 0,
            "failed_ai_insights": 0,
            "learning_events": 0
        }

    async def initialize(self):
        """Initialize the AI processor."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("ai_pattern_processor_initialization"):
                    # Initialize embedders if not already done
                    if not self._embedders_initialized:
                        await code_embedder.initialize()
                        await doc_embedder.initialize()
                        await arch_embedder.initialize()
                        self._embedders_initialized = True
                    
                    self._initialized = True
                    await log("AI pattern processor initialized", level="info")
            except Exception as e:
                await log(f"Error initializing AI pattern processor: {e}", level="error")
                raise

    async def initialize_integration(self, pattern_integration):
        """Initialize pattern integration layer."""
        self._pattern_integration = pattern_integration

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI capabilities."""
        if not self._initialized:
            await self.initialize()

        try:
            self._metrics["total_ai_processed"] += 1

            # Get base patterns from core processor
            patterns = await self.base_processor.process_for_purpose(
                source_code,
                self._get_purpose_from_context(context),
                context.project.file_type,
                self._get_categories_from_context(context)
            )

            # Process with AI capabilities
            results = await self._enhance_with_ai(patterns, context)
            
            # Update metrics
            if results.success:
                self._metrics["successful_ai_insights"] += 1
            else:
                self._metrics["failed_ai_insights"] += 1

            return results

        except Exception as e:
            await log(f"Error in AI pattern processing: {e}", level="error")
            self._metrics["failed_ai_insights"] += 1
            return AIProcessingResult(
                success=False,
                response=f"Error in AI processing: {str(e)}"
            )

    def _get_purpose_from_context(self, context: AIContext) -> PatternPurpose:
        """Map interaction type to pattern purpose."""
        purpose_map = {
            InteractionType.QUESTION: PatternPurpose.EXPLANATION,
            InteractionType.MODIFICATION: PatternPurpose.MODIFICATION,
            InteractionType.ERROR: PatternPurpose.DEBUGGING,
            InteractionType.COMPLETION: PatternPurpose.COMPLETION,
            InteractionType.EXPLANATION: PatternPurpose.EXPLANATION,
            InteractionType.SUGGESTION: PatternPurpose.SUGGESTION,
            InteractionType.DOCUMENTATION: PatternPurpose.DOCUMENTATION
        }
        return purpose_map.get(context.interaction.interaction_type, PatternPurpose.UNDERSTANDING)

    def _get_categories_from_context(self, context: AIContext) -> List[PatternCategory]:
        """Get relevant pattern categories based on context."""
        category_map = {
            InteractionType.QUESTION: [PatternCategory.CONTEXT, PatternCategory.SEMANTICS],
            InteractionType.MODIFICATION: [PatternCategory.SYNTAX, PatternCategory.CODE_PATTERNS],
            InteractionType.ERROR: [PatternCategory.COMMON_ISSUES, PatternCategory.SYNTAX],
            InteractionType.COMPLETION: [PatternCategory.USER_PATTERNS, PatternCategory.CODE_PATTERNS],
            InteractionType.EXPLANATION: [PatternCategory.CONTEXT, PatternCategory.DOCUMENTATION],
            InteractionType.SUGGESTION: [PatternCategory.BEST_PRACTICES, PatternCategory.USER_PATTERNS],
            InteractionType.DOCUMENTATION: [PatternCategory.DOCUMENTATION, PatternCategory.CONTEXT]
        }
        return category_map.get(context.interaction.interaction_type, [])

    async def _enhance_with_ai(
        self,
        patterns: List[ProcessedPattern],
        context: AIContext
    ) -> AIProcessingResult:
        """Enhance pattern processing results with AI capabilities."""
        results = AIProcessingResult(
            success=True,
            response=None,
            suggestions=[],
            context_info={},
            confidence=0.0,
            learned_patterns=[],
            ai_insights={}
        )

        for pattern in patterns:
            # Calculate AI-enhanced confidence
            confidence = await self._calculate_ai_confidence(pattern, context)
            
            # Generate AI insights
            insights = await self._generate_ai_insights(pattern, context)
            if insights:
                results.ai_insights[pattern.pattern_name] = insights

            # Apply AI-specific processing based on confidence
            if confidence >= 0.8:
                results.response = await self._generate_ai_response(pattern, context)
                results.confidence = confidence
            elif confidence >= 0.5:
                suggestion = await self._generate_ai_suggestion(pattern, context)
                results.suggestions.append(suggestion)
            
            # Learn from pattern if learning capability is enabled
            if AICapability.LEARNING in self.capabilities:
                learned = await self._learn_from_pattern(pattern, confidence)
                if learned:
                    results.learned_patterns.append(learned)
                    self._metrics["learning_events"] += 1

        return results

    async def _calculate_ai_confidence(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate AI-enhanced confidence score."""
        base_confidence = pattern.confidence if hasattr(pattern, 'confidence') else 0.5
        
        # Add AI-specific confidence metrics
        ai_metrics = {
            "context_relevance": await self._calculate_context_relevance(pattern, context),
            "user_history": await self._calculate_user_history_confidence(pattern, context),
            "project_relevance": await self._calculate_project_relevance(pattern, context)
        }
        
        # Weight and combine metrics
        weights = {
            "base_confidence": 0.4,
            "context_relevance": 0.3,
            "user_history": 0.2,
            "project_relevance": 0.1
        }
        
        confidence = (
            base_confidence * weights["base_confidence"] +
            ai_metrics["context_relevance"] * weights["context_relevance"] +
            ai_metrics["user_history"] * weights["user_history"] +
            ai_metrics["project_relevance"] * weights["project_relevance"]
        )
        
        return min(confidence, 1.0)

    async def cleanup(self):
        """Clean up AI processor resources."""
        try:
            self._pattern_memory.clear()
            self._interaction_history.clear()
            self._initialized = False
            self._embedders_initialized = False
            await log("AI pattern processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up AI pattern processor: {e}", level="error")

    def get_metrics(self) -> Dict[str, Any]:
        """Get AI processing metrics."""
        return self._metrics.copy()

# Global instance
ai_pattern_processor = None

async def get_ai_pattern_processor() -> AIPatternProcessor:
    """Get the global AI pattern processor instance."""
    global ai_pattern_processor
    if ai_pattern_processor is None:
        base_processor = await PatternProcessor.create()
        ai_pattern_processor = AIPatternProcessor(base_processor)
        await ai_pattern_processor.initialize()
    return ai_pattern_processor 