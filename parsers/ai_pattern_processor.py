"""AI pattern processor for RepoAnalyzer.

This module provides AI-powered pattern processing capabilities, including pattern
matching, analysis, and enhancement.
"""

from typing import Dict, Any, List, Optional, Union, Set
import asyncio
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_mapping import normalize_language_name
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
import time
from db.transaction import transaction_scope
from parsers.query_patterns.enhanced_patterns import (
    PatternContext, PatternPerformanceMetrics,
    AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
)

class AIPatternProcessor:
    """AI pattern processor that handles pattern analysis and enhancement."""
    
    def __init__(self):
        """Initialize AI pattern processor."""
        self._initialized = False
        self._cache = None
        self._metrics = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "processing_times": []
        }
        self._pattern_learner = None
        self._adaptive_patterns: Dict[str, AdaptivePattern] = {}
        self._resilient_patterns: Dict[str, ResilientPattern] = {}
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the AI pattern processor is initialized."""
        if not self._initialized:
            raise ProcessingError("AI pattern processor not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'AIPatternProcessor':
        """Create and initialize an AI pattern processor instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("ai_pattern_processor_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "ai_pattern_processor",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("ai_pattern_processor")
                await cache_coordinator.register_cache(instance._cache)
                
                # Initialize pattern learner
                instance._pattern_learner = CrossProjectPatternLearner()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log("AI pattern processor initialized", level="info")
                
                # Update final status
                await global_health_monitor.update_component_status(
                    "ai_pattern_processor",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing AI pattern processor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "ai_pattern_processor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize AI pattern processor: {e}")
    
    async def learn_from_project(self, project_path: str) -> Dict[str, Any]:
        """Learn patterns from a project codebase."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            start_time = time.time()
            
            # Use pattern learner to extract patterns
            await self._pattern_learner.learn_from_project(project_path)
            
            # Get learned patterns
            learned_patterns = await self._pattern_learner.suggest_patterns(
                PatternContext(file_location=project_path)
            )
            
            # Convert to adaptive and resilient patterns
            for pattern in learned_patterns:
                pattern_key = f"{pattern.name}:{pattern.language_id}"
                
                # Create adaptive pattern
                adaptive_pattern = AdaptivePattern(
                    name=pattern.name,
                    pattern=pattern.pattern,
                    category=pattern.category,
                    purpose=pattern.purpose,
                    language_id=pattern.language_id
                )
                self._adaptive_patterns[pattern_key] = adaptive_pattern
                
                # Create resilient pattern
                resilient_pattern = ResilientPattern(
                    name=pattern.name,
                    pattern=pattern.pattern,
                    category=pattern.category,
                    purpose=pattern.purpose,
                    language_id=pattern.language_id
                )
                self._resilient_patterns[pattern_key] = resilient_pattern
            
            processing_time = time.time() - start_time
            
            return {
                "learned_patterns": len(learned_patterns),
                "processing_time": processing_time,
                "project": project_path
            }
            
        except Exception as e:
            await log(f"Error learning from project: {e}", level="error")
            return {
                "error": str(e),
                "project": project_path
            }

    async def process_with_adaptive_patterns(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code using adaptive patterns."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            start_time = time.time()
            
            # Create pattern context
            pattern_context = PatternContext(
                code_structure=context.code_structure if hasattr(context, 'code_structure') else {},
                language_stats=context.language_stats if hasattr(context, 'language_stats') else {},
                project_patterns=context.project_patterns if hasattr(context, 'project_patterns') else [],
                file_location=context.file_path if hasattr(context, 'file_path') else "",
                dependencies=set(context.dependencies) if hasattr(context, 'dependencies') else set(),
                recent_changes=context.recent_changes if hasattr(context, 'recent_changes') else []
            )
            
            results = []
            for pattern in self._adaptive_patterns.values():
                try:
                    matches = await pattern.matches(source_code, pattern_context)
                    if matches:
                        results.extend(matches)
                except Exception as e:
                    await log(f"Error in adaptive pattern {pattern.name}: {e}", level="error")
            
            processing_time = time.time() - start_time
            
            return AIProcessingResult(
                success=True,
                matches=results,
                processing_time=processing_time,
                metadata={
                    "patterns_used": len(self._adaptive_patterns),
                    "matches_found": len(results)
                }
            )
            
        except Exception as e:
            await log(f"Error in adaptive pattern processing: {e}", level="error")
            return AIProcessingResult(
                success=False,
                error=str(e)
            )

    async def process_with_error_recovery(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with error recovery capabilities."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            start_time = time.time()
            
            # Create pattern context
            pattern_context = PatternContext(
                code_structure=context.code_structure if hasattr(context, 'code_structure') else {},
                language_stats=context.language_stats if hasattr(context, 'language_stats') else {},
                project_patterns=context.project_patterns if hasattr(context, 'project_patterns') else [],
                file_location=context.file_path if hasattr(context, 'file_path') else "",
                dependencies=set(context.dependencies) if hasattr(context, 'dependencies') else set(),
                recent_changes=context.recent_changes if hasattr(context, 'recent_changes') else []
            )
            
            results = []
            recovery_stats = {
                "attempts": 0,
                "successful_recoveries": 0,
                "failed_recoveries": 0
            }
            
            for pattern in self._resilient_patterns.values():
                try:
                    matches = await pattern.matches(source_code, pattern_context)
                    if matches:
                        results.extend(matches)
                except Exception as e:
                    recovery_stats["attempts"] += 1
                    try:
                        # Attempt recovery
                        recovered_matches = await pattern._handle_error(source_code, e)
                        if recovered_matches:
                            results.extend(recovered_matches)
                            recovery_stats["successful_recoveries"] += 1
                        else:
                            recovery_stats["failed_recoveries"] += 1
                    except Exception as recovery_error:
                        await log(f"Error recovery failed for pattern {pattern.name}: {recovery_error}", level="error")
                        recovery_stats["failed_recoveries"] += 1
            
            processing_time = time.time() - start_time
            
            return AIProcessingResult(
                success=True,
                matches=results,
                processing_time=processing_time,
                metadata={
                    "patterns_used": len(self._resilient_patterns),
                    "matches_found": len(results),
                    "recovery_stats": recovery_stats
                }
            )
            
        except Exception as e:
            await log(f"Error in resilient pattern processing: {e}", level="error")
            return AIProcessingResult(
                success=False,
                error=str(e)
            )

    async def verify_patterns(self, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify and test patterns against test cases."""
        if not self._initialized:
            await self.ensure_initialized()
            
        verification_results = {
            "verified_patterns": [],
            "failed_patterns": [],
            "verification_time": 0,
            "stats": {
                "total": len(patterns),
                "verified": 0,
                "failed": 0
            }
        }
        
        start_time = time.time()
        
        for pattern_data in patterns:
            try:
                # Create test pattern
                test_pattern = ResilientPattern(
                    name=pattern_data["name"],
                    pattern=pattern_data["pattern"],
                    category=pattern_data.get("category"),
                    purpose=pattern_data.get("purpose"),
                    language_id=pattern_data.get("language_id")
                )
                
                # Run test cases if provided
                test_cases = pattern_data.get("test_cases", [])
                test_results = []
                
                for test_case in test_cases:
                    try:
                        matches = await test_pattern.matches(
                            test_case["input"],
                            PatternContext(file_location="test")
                        )
                        test_results.append({
                            "case": test_case["name"],
                            "success": bool(matches),
                            "matches": len(matches)
                        })
                    except Exception as e:
                        test_results.append({
                            "case": test_case["name"],
                            "success": False,
                            "error": str(e)
                        })
                
                # Evaluate results
                success_rate = sum(1 for r in test_results if r["success"]) / len(test_results) if test_results else 0
                
                if success_rate >= 0.8:  # 80% success threshold
                    verification_results["verified_patterns"].append({
                        "pattern": pattern_data["name"],
                        "success_rate": success_rate,
                        "test_results": test_results
                    })
                    verification_results["stats"]["verified"] += 1
                else:
                    verification_results["failed_patterns"].append({
                        "pattern": pattern_data["name"],
                        "success_rate": success_rate,
                        "test_results": test_results
                    })
                    verification_results["stats"]["failed"] += 1
                    
            except Exception as e:
                verification_results["failed_patterns"].append({
                    "pattern": pattern_data["name"],
                    "error": str(e)
                })
                verification_results["stats"]["failed"] += 1
        
        verification_results["verification_time"] = time.time() - start_time
        
        return verification_results

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process source code with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            start_time = time.time()
            
            # Create pattern context
            pattern_context = PatternContext(
                code_structure=context.code_structure if hasattr(context, 'code_structure') else {},
                language_stats=context.language_stats if hasattr(context, 'language_stats') else {},
                project_patterns=context.project_patterns if hasattr(context, 'project_patterns') else [],
                file_location=context.file_path if hasattr(context, 'file_path') else "",
                dependencies=set(context.dependencies) if hasattr(context, 'dependencies') else set(),
                recent_changes=context.recent_changes if hasattr(context, 'recent_changes') else []
            )
            
            # Get pattern integration instance
            from ai_tools.pattern_integration import get_pattern_integration
            pattern_integration = await get_pattern_integration()
            
            # First try adaptive patterns
            adaptive_results = await self.process_with_adaptive_patterns(source_code, context)
            
            # Then try with error recovery if needed
            if not adaptive_results.success or not adaptive_results.matches:
                resilient_results = await self.process_with_error_recovery(source_code, context)
                if resilient_results.success and resilient_results.matches:
                    adaptive_results.matches.extend(resilient_results.matches)
                    adaptive_results.metadata["recovery_applied"] = True
            
            # Finally process using pattern integration with enhanced patterns
            integration_results = await pattern_integration.process_interaction(
                source_code,
                context,
                pattern_context=pattern_context
            )
            
            # Combine results
            combined_matches = []
            if adaptive_results.success:
                combined_matches.extend(adaptive_results.matches)
            if integration_results.success:
                combined_matches.extend(integration_results.matches)
            
            # Update metrics
            self._metrics["total_processed"] += 1
            self._metrics["processing_times"].append(time.time() - start_time)
            if combined_matches:
                self._metrics["successful_processing"] += 1
            else:
                self._metrics["failed_processing"] += 1
            
            return AIProcessingResult(
                success=True,
                matches=combined_matches,
                processing_time=time.time() - start_time,
                metadata={
                    "adaptive_results": adaptive_results.metadata if adaptive_results.success else None,
                    "integration_results": integration_results.metadata if integration_results.success else None,
                    "total_matches": len(combined_matches)
                }
            )
            
        except Exception as e:
            await log(f"Error in AI pattern processing: {e}", level="error")
            self._metrics["failed_processing"] += 1
            return AIProcessingResult(
                success=False,
                response=f"Error in AI pattern processing: {str(e)}"
            )

    async def get_metrics(self) -> Dict[str, Any]:
        """Get AI pattern processor metrics."""
        metrics = {
            "processing_metrics": self._metrics,
            "cache_stats": {
                "hits": self._metrics["cache_hits"],
                "misses": self._metrics["cache_misses"],
                "hit_rate": (
                    self._metrics["cache_hits"] / 
                    (self._metrics["cache_hits"] + self._metrics["cache_misses"])
                    if (self._metrics["cache_hits"] + self._metrics["cache_misses"]) > 0
                    else 0
                )
            }
        }
        
        # Add pattern learner metrics if available
        if self._pattern_learner:
            metrics["pattern_learner"] = {
                "total_patterns": len(self._pattern_learner.pattern_database),
                "projects": len(self._pattern_learner.project_stats)
            }
            
        return metrics
    
    async def cleanup(self):
        """Clean up AI pattern processor resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "ai_pattern_processor",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache("ai_pattern_processor")
                self._cache = None
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            
            self._initialized = False
            await log("AI pattern processor cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "ai_pattern_processor",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up AI pattern processor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "ai_pattern_processor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup AI pattern processor: {e}")

# Create singleton instance
ai_pattern_processor = None

async def get_ai_pattern_processor() -> AIPatternProcessor:
    """Get or create the AI pattern processor singleton instance."""
    global ai_pattern_processor
    if ai_pattern_processor is None:
        ai_pattern_processor = await AIPatternProcessor.create()
    return ai_pattern_processor

# Export public interfaces
__all__ = [
    'AIPatternProcessor',
    'get_ai_pattern_processor',
    'ai_pattern_processor'
] 