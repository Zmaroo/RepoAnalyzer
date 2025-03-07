"""AI-specific pattern processing system."""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import asyncio
from parsers.types import (
    PatternCategory, PatternPurpose, FileType,
    InteractionType, ConfidenceLevel,
    AIContext, AIProcessingResult,
    AICapability, AIConfidenceMetrics,
    get_purpose_from_interaction,
    get_categories_from_interaction
)
from parsers.pattern_processor import PatternProcessor, ProcessedPattern
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity, ProcessingError
from utils.async_runner import submit_async_task
from embedding.embedding_models import code_embedder, doc_embedder, arch_embedder
from db.transaction import transaction_scope
from db.graph_sync import graph_sync
from utils.cache import UnifiedCache, cache_coordinator, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from utils.error_handling import ErrorAudit
import time
import numpy as np
import psutil
import os

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
        self._cache = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._warmup_complete = False

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
                    
                    # Initialize cache
                    self._cache = UnifiedCache("ai_pattern_processor", ttl=3600)
                    await cache_coordinator.register_cache(self._cache)
                    
                    # Initialize cache analytics
                    analytics = await get_cache_analytics()
                    analytics.register_warmup_function(
                        "ai_pattern_processor",
                        self._warmup_cache
                    )
                    
                    # Enable cache optimization
                    await analytics.optimize_ttl_values()
                    
                    # Register with health monitor
                    global_health_monitor.register_component(
                        "ai_pattern_processor",
                        health_check=self._check_health
                    )
                    
                    # Initialize error analysis
                    await ErrorAudit.analyze_codebase(os.path.dirname(__file__))
                    
                    # Start warmup task
                    warmup_task = asyncio.create_task(self._warmup_caches())
                    self._pending_tasks.add(warmup_task)
                    
                    self._initialized = True
                    await log("AI pattern processor initialized", level="info")
            except Exception as e:
                await log(f"Error initializing AI pattern processor: {e}", level="error")
                raise

    async def _warmup_caches(self):
        """Warm up caches with frequently used patterns."""
        try:
            # Get frequently used patterns
            async with transaction_scope() as txn:
                patterns = await txn.fetch("""
                    SELECT pattern_name, usage_count
                    FROM ai_pattern_usage_stats
                    WHERE usage_count > 10
                    ORDER BY usage_count DESC
                    LIMIT 100
                """)
                
                # Warm up pattern cache
                for pattern in patterns:
                    await self._warmup_cache([pattern["pattern_name"]])
                    
            self._warmup_complete = True
            await log("AI pattern cache warmup complete", level="info")
        except Exception as e:
            await log(f"Error warming up caches: {e}", level="error")

    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for AI pattern cache."""
        results = {}
        for key in keys:
            try:
                pattern = await self._get_pattern(key)
                if pattern:
                    results[key] = pattern
            except Exception as e:
                await log(f"Error warming up pattern {key}: {e}", level="warning")
        return results

    async def _check_health(self) -> Dict[str, Any]:
        """Health check for AI pattern processor."""
        # Get error audit data
        error_report = await ErrorAudit.get_error_report()
        
        # Get cache analytics
        analytics = await get_cache_analytics()
        cache_stats = await analytics.get_metrics()
        
        # Get resource usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": self._metrics,
            "embedders_initialized": self._embedders_initialized,
            "cache_stats": {
                "hit_rates": cache_stats.get("hit_rates", {}),
                "memory_usage": cache_stats.get("memory_usage", {}),
                "eviction_rates": cache_stats.get("eviction_rates", {})
            },
            "error_stats": {
                "total_errors": error_report.get("total_errors", 0),
                "error_rate": error_report.get("error_rate", 0),
                "top_errors": error_report.get("top_error_locations", [])[:3]
            },
            "resource_usage": {
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "cpu_percent": process.cpu_percent(),
                "thread_count": len(process.threads())
            },
            "warmup_status": {
                "complete": self._warmup_complete,
                "cache_ready": self._warmup_complete and self._cache is not None
            }
        }
        
        # Check for degraded conditions
        if self._metrics["failed_ai_insights"] > self._metrics["total_ai_processed"] * 0.2:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High AI insight failure rate"
        elif error_report.get("error_rate", 0) > 0.1:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High error rate"
        elif details["resource_usage"]["cpu_percent"] > 80:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High CPU usage"
        elif not self._embedders_initialized:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Embedders not initialized"
        elif not self._warmup_complete:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Cache warmup incomplete"
            
        return {
            "status": status,
            "details": details
        }

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
                get_purpose_from_interaction(context.interaction.interaction_type),
                context.project.file_type,
                get_categories_from_interaction(context.interaction.interaction_type)
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
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up embedders
            if self._embedders_initialized:
                await code_embedder.cleanup()
                await doc_embedder.cleanup()
                await arch_embedder.cleanup()
                self._embedders_initialized = False
            
            # Clean up cache
            if self._cache:
                await self._cache.clear_async()
                await cache_coordinator.unregister_cache("ai_pattern_processor")
            
            # Save error analysis
            await ErrorAudit.save_report()
            
            # Save cache analytics
            analytics = await get_cache_analytics()
            await analytics.save_metrics_history(self._cache.get_metrics())
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO ai_pattern_processor_metrics (
                        timestamp, total_processed, successful_insights,
                        failed_insights, learning_events
                    ) VALUES ($1, $2, $3, $4, $5)
                """, (
                    time.time(),
                    self._metrics["total_ai_processed"],
                    self._metrics["successful_ai_insights"],
                    self._metrics["failed_ai_insights"],
                    self._metrics["learning_events"]
                ))
            
            # Clear memory and history
            self._pattern_memory.clear()
            self._interaction_history.clear()
            
            # Unregister from health monitor
            global_health_monitor.unregister_component("ai_pattern_processor")
            
            self._initialized = False
            await log("AI pattern processor cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up AI pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup AI pattern processor: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get AI processing metrics."""
        return self._metrics.copy()

    async def _learn_from_pattern(
        self,
        pattern: ProcessedPattern,
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """Learn from a pattern and track similarities."""
        if not pattern or confidence < 0.5:
            return None
            
        try:
            # Validate pattern first with context
            validation_context = {
                "purpose": PatternPurpose.LEARNING,
                "confidence_threshold": confidence,
                "capabilities": self.capabilities,
                "learning_history": self._interaction_history[-10:] if self._interaction_history else []
            }
            
            is_valid, errors = await self.base_processor.validate_pattern(
                pattern,
                validation_context=validation_context,
                skip_cache=False  # Use cache for better performance
            )
            
            if not is_valid:
                error_context = {
                    "pattern_name": pattern.pattern_name,
                    "confidence": confidence,
                    "validation_errors": errors,
                    "capabilities": list(self.capabilities)
                }
                await log(f"Invalid pattern for learning: {error_context}", level="warning")
                return None
            
            # Get validation stats for monitoring
            validation_stats = await self.base_processor.get_validation_stats()
            if validation_stats["total_validations"] > 100:  # Only log after sufficient data
                await log(
                    f"Pattern validation stats: success_rate={validation_stats.get('success_rate', 0):.2f}, "
                    f"cache_hit_rate={validation_stats.get('cache_hit_rate', 0):.2f}",
                    level="info"
                )
            
            # Create pattern embedding
            pattern_text = pattern.content if hasattr(pattern, 'content') else str(pattern)
            embedding = await code_embedder.embed_with_retry(
                pattern_text,
                pattern_type=pattern.pattern_type if hasattr(pattern, 'pattern_type') else None
            )
            
            # Store pattern with embedding
            async with transaction_scope() as txn:
                pattern_data = {
                    "pattern_type": pattern.pattern_type,
                    "content": pattern_text,
                    "confidence": confidence,
                    "embedding": embedding.tolist() if hasattr(embedding, 'tolist') else None,
                    "metadata": {
                        "source": "ai_learning",
                        "timestamp": time.time(),
                        "original_confidence": pattern.confidence if hasattr(pattern, 'confidence') else None,
                        "validation_context": validation_context,
                        "validation_success_rate": validation_stats.get("success_rate", 0)
                    }
                }
                
                # Store in Neo4j for similarity tracking
                await graph_sync.store_pattern_node(pattern_data)
                
                # Update pattern memory
                self._pattern_memory[pattern.pattern_name] = confidence
                
                # Track learning event with validation info
                self._interaction_history.append({
                    "pattern_name": pattern.pattern_name,
                    "confidence": confidence,
                    "timestamp": time.time(),
                    "validation_success": True,
                    "validation_stats": {
                        "success_rate": validation_stats.get("success_rate", 0),
                        "cache_hit_rate": validation_stats.get("cache_hit_rate", 0)
                    }
                })
                
                return pattern_data
                
        except Exception as e:
            await log(f"Error learning from pattern: {e}", level="error")
            return None

    async def _calculate_pattern_similarity(
        self,
        pattern: ProcessedPattern,
        embedding: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Calculate pattern similarities using Neo4j vector search."""
        try:
            # Query Neo4j for similar patterns
            similar_patterns = await graph_sync.find_similar_patterns(
                embedding.tolist(),
                limit=5,
                min_similarity=0.7
            )
            
            # Process and return similarities
            return [{
                "pattern_id": p["pattern_id"],
                "similarity": p["similarity"],
                "pattern_type": p["pattern_type"]
            } for p in similar_patterns]
            
        except Exception as e:
            await log(f"Error calculating pattern similarity: {e}", level="error")
            return []

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