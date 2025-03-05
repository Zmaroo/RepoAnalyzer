"""Integration layer between pattern processing and AI tools."""

from typing import Dict, Any, List, Optional, Set, Tuple
import asyncio
from dataclasses import dataclass
from parsers.types import (
    PatternCategory, PatternPurpose, FileType,
    InteractionType, ConfidenceLevel,
    AIAssistantContext, Documentation, ComplexityMetrics,
    AICapability
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
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from db.pattern_storage import pattern_storage

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
        """Private constructor - use create() instead."""
        self.ai_interface = None
        self.code_understanding = None
        self.graph_capabilities = None
        self.rule_config = None
        self._pattern_processor = None
        self._ai_processor = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._initialized = False
        self._deep_learning_results: Dict[str, Dict[str, Any]] = {}  # Cache for deep learning results
        self._pattern_learning_cache: Dict[str, Dict[str, Any]] = {}  # Cache for pattern learning results
        self._learning_metrics = PatternLearningMetrics()
        self._pattern_storage = None
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("PatternIntegration not initialized. Use create() to initialize.")
        if not self.ai_interface:
            raise ProcessingError("AI interface not initialized")
        if not self.code_understanding:
            raise ProcessingError("Code understanding not initialized")
        if not self.graph_capabilities:
            raise ProcessingError("Graph capabilities not initialized")
        if not self._pattern_storage:
            raise ProcessingError("Pattern storage not initialized")
        if not self._pattern_processor:
            raise ProcessingError("Pattern processor not initialized")
        if not self._ai_processor:
            raise ProcessingError("AI processor not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'PatternIntegration':
        """Async factory method to create and initialize a PatternIntegration instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="pattern integration initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize AI interface
                from .ai_interface import AIInterface
                instance.ai_interface = await AIInterface.create()
                
                # Initialize code understanding
                from .code_understanding import CodeUnderstanding
                instance.code_understanding = await CodeUnderstanding.create()
                
                # Initialize graph capabilities
                from .graph_capabilities import GraphAnalysis
                instance.graph_capabilities = await GraphAnalysis.create()
                
                # Initialize rule config
                from .rule_config import RuleConfig
                instance.rule_config = RuleConfig()
                
                # Initialize pattern storage
                from db.pattern_storage import get_pattern_storage
                instance._pattern_storage = await get_pattern_storage()
                
                # Initialize pattern processor
                from parsers.pattern_processor import PatternProcessor
                instance._pattern_processor = await PatternProcessor.create()
                
                # Initialize AI processor
                from parsers.ai_pattern_processor import AIPatternProcessor
                instance._ai_processor = AIPatternProcessor(instance._pattern_processor)
                await instance._ai_processor.initialize_integration(instance)
                
                # Register shutdown handler
                from utils.shutdown import register_shutdown_handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("pattern_integration")
                
                instance._initialized = True
                await log("Pattern integration initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing pattern integration: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize pattern integration: {e}")
    
    async def process_interaction(
        self,
        source_code: str,
        context: AIAssistantContext
    ) -> Dict[str, Any]:
        """Process interaction using all available tools."""
        if not self._initialized:
            await self.ensure_initialized()
        
        async with AsyncErrorBoundary("pattern integration processing"):
            # Process with pattern processor
            pattern_results = await self._pattern_processor.process_with_ai(
                source_code,
                context
            )
            
            # Get code context
            code_context = await self.code_understanding.get_code_context(
                source_code,
                context
            )
            
            # Get graph insights
            graph_insights = await self.graph_capabilities.get_graph_insights(
                source_code,
                context
            )
            
            # Get learned patterns
            learned_patterns = await reference_learning.get_learned_patterns(
                source_code,
                context
            )
            
            # Enhance results with AI tool insights
            task = asyncio.create_task(self._enhance_results(
                pattern_results,
                code_context,
                graph_insights,
                learned_patterns,
                context
            ))
            self._pending_tasks.add(task)
            try:
                enhanced_results = await task
            finally:
                self._pending_tasks.remove(task)
            
            # Learn from interaction
            task = asyncio.create_task(reference_learning.learn_from_interaction(
                source_code,
                pattern_results.get("patterns_used", []),
                enhanced_results,
                context
            ))
            self._pending_tasks.add(task)
            try:
                await task
            finally:
                self._pending_tasks.remove(task)
            
            return enhanced_results
    
    @handle_async_errors(error_types=(ProcessingError,))
    async def learn_patterns_from_reference(
        self,
        reference_repo_id: int,
        target_repo_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Learn patterns from a reference repository and optionally apply them to a target repository."""
        # Check cache first
        cache_key = f"pattern_learning:{reference_repo_id}:{target_repo_id or 'none'}"
        if cache_key in self._pattern_learning_cache:
            return self._pattern_learning_cache[cache_key]

        # Extract patterns from reference repository
        patterns = await self._extract_reference_patterns(reference_repo_id)
        
        # Analyze patterns
        analysis = await self._analyze_patterns(patterns)
        
        # Apply patterns to target if specified
        application_results = None
        if target_repo_id:
            application_results = await self._apply_patterns_to_target(
                patterns,
                target_repo_id
            )
        
        # Store patterns
        await self._pattern_storage.store_patterns(reference_repo_id, {
            "code": [p for p in patterns if p["type"] == "code"],
            "doc": [p for p in patterns if p["type"] == "doc"],
            "arch": [p for p in patterns if p["type"] == "arch"]
        })
        
        # Update metrics
        await self._update_learning_metrics(patterns)
        
        # Store results
        results = {
            "patterns": patterns,
            "analysis": analysis,
            "application_results": application_results,
            "metrics": self._learning_metrics
        }
        self._pattern_learning_cache[cache_key] = results
        
        return results
    
    @handle_async_errors(error_types=(ProcessingError,))
    async def deep_learn_from_multiple_repositories(
        self,
        repo_ids: List[int],
        context: AIAssistantContext
    ) -> Dict[str, Any]:
        """Deep learn from multiple repositories by analyzing cross-repository patterns."""
        if len(repo_ids) < 2:
            raise ProcessingError("At least two repositories are required for deep learning")
        
        # Check cache first
        cache_key = f"deep_learning:{','.join(map(str, sorted(repo_ids)))}"
        if cache_key in self._deep_learning_results:
            return self._deep_learning_results[cache_key]

        # Get patterns from all repositories
        all_patterns = {}
        for repo_id in repo_ids:
            patterns = await self._pattern_storage.get_patterns(repo_id)
            all_patterns[repo_id] = patterns
        
        # Find common patterns across repositories
        common_patterns = await self._find_common_patterns(all_patterns)
        
        # Analyze relationships between patterns
        relationships = await self._analyze_pattern_relationships(common_patterns)
        
        # Generate insights
        insights = await self._generate_pattern_insights(common_patterns, relationships)
        
        # Store results
        results = {
            "common_patterns": common_patterns,
            "relationships": relationships,
            "insights": insights,
            "metrics": self._learning_metrics
        }
        self._deep_learning_results[cache_key] = results
        
        return results
    
    async def _find_common_patterns(
        self,
        all_patterns: Dict[int, Dict[str, List[Dict[str, Any]]]]
    ) -> List[Dict[str, Any]]:
        """Find patterns that are common across repositories."""
        common_patterns = []
        
        # Get all pattern types
        pattern_types = set()
        for patterns in all_patterns.values():
            for type_patterns in patterns.values():
                pattern_types.update(p["type"] for p in type_patterns)
        
        # Find common patterns for each type
        for pattern_type in pattern_types:
            type_patterns = []
            for repo_id, patterns in all_patterns.items():
                for type_patterns_list in patterns.values():
                    type_patterns.extend([
                        (repo_id, p) for p in type_patterns_list
                        if p["type"] == pattern_type
                    ])
            
            if len(type_patterns) >= 2:  # Pattern exists in at least 2 repos
                # Group similar patterns
                pattern_groups = self._group_similar_patterns(type_patterns)
                
                # Add common patterns
                for group in pattern_groups:
                    if len(group) >= 2:  # At least 2 similar patterns
                        common_pattern = self._create_common_pattern(group)
                        common_patterns.append(common_pattern)
        
        return common_patterns
    
    async def _analyze_pattern_relationships(
        self,
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze relationships between patterns."""
        relationships = {
            "dependencies": [],
            "similarities": [],
            "conflicts": []
        }
        
        # Analyze each pair of patterns
        for i, pattern1 in enumerate(patterns):
            for pattern2 in patterns[i + 1:]:
                # Check dependencies
                if self._ai_processor._are_patterns_dependent(pattern1, pattern2):
                    strength = self._ai_processor._calculate_dependency_strength(pattern1, pattern2)
                    relationships["dependencies"].append({
                        "source": pattern1["id"],
                        "target": pattern2["id"],
                        "strength": strength
                    })
                
                # Check similarities
                similarity = self._ai_processor._calculate_pattern_similarity(pattern1, pattern2)
                if similarity > 0.7:  # High similarity threshold
                    relationships["similarities"].append({
                        "pattern1": pattern1["id"],
                        "pattern2": pattern2["id"],
                        "similarity": similarity
                    })
                
                # Check conflicts
                if self._ai_processor._are_patterns_conflicting(pattern1, pattern2):
                    relationships["conflicts"].append({
                        "pattern1": pattern1["id"],
                        "pattern2": pattern2["id"],
                        "severity": self._calculate_conflict_severity(pattern1, pattern2)
                    })
        
        return relationships
    
    async def _generate_pattern_insights(
        self,
        patterns: List[Dict[str, Any]],
        relationships: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate insights from patterns and their relationships."""
        insights = {
            "pattern_usage": {},
            "best_practices": [],
            "potential_issues": [],
            "recommendations": []
        }
        
        # Analyze pattern usage
        for pattern in patterns:
            insights["pattern_usage"][pattern["id"]] = {
                "frequency": pattern.get("frequency", 0),
                "repositories": pattern.get("repositories", []),
                "confidence": pattern.get("confidence", 0.0)
            }
        
        # Identify best practices
        insights["best_practices"] = await self._identify_best_practices(patterns)
        
        # Identify potential issues
        insights["potential_issues"] = await self._identify_potential_issues(patterns, relationships)
        
        # Generate recommendations
        insights["recommendations"] = await self._generate_recommendations(patterns, relationships)
        
        return insights
    
    async def _identify_best_practices(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify best practices from patterns."""
        best_practices = []
        
        for pattern in patterns:
            # Check pattern quality metrics
            quality_metrics = await self._calculate_complexity_metrics([pattern])
            
            if (
                quality_metrics["maintainability_score"] > 0.8 and
                quality_metrics["reusability_score"] > 0.8 and
                pattern.get("frequency", 0) >= 3  # Used in at least 3 repos
            ):
                best_practices.append({
                    "pattern_id": pattern["id"],
                    "name": pattern["name"],
                    "description": pattern.get("description", ""),
                    "metrics": quality_metrics,
                    "frequency": pattern.get("frequency", 0)
                })
        
        return best_practices
    
    async def _identify_potential_issues(
        self,
        patterns: List[Dict[str, Any]],
        relationships: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify potential issues from patterns and relationships."""
        issues = []
        
        # Check for conflicts
        for conflict in relationships["conflicts"]:
            issues.append({
                "type": "pattern_conflict",
                "severity": conflict["severity"],
                "patterns": [conflict["pattern1"], conflict["pattern2"]],
                "description": "Conflicting patterns detected"
            })
        
        # Check for complex patterns
        for pattern in patterns:
            metrics = await self._calculate_complexity_metrics([pattern])
            if metrics["average_complexity"] > 0.8:
                issues.append({
                    "type": "high_complexity",
                    "severity": "medium",
                    "pattern_id": pattern["id"],
                    "description": "Pattern has high complexity"
                })
        
        return issues
    
    async def _generate_recommendations(
        self,
        patterns: List[Dict[str, Any]],
        relationships: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on patterns and relationships."""
        recommendations = []
        
        # Recommend best practices
        best_practices = await self._identify_best_practices(patterns)
        for practice in best_practices:
            recommendations.append({
                "type": "best_practice",
                "priority": "high",
                "pattern_id": practice["pattern_id"],
                "description": f"Consider using {practice['name']} pattern"
            })
        
        # Recommend resolving conflicts
        for conflict in relationships["conflicts"]:
            recommendations.append({
                "type": "resolve_conflict",
                "priority": "medium",
                "patterns": [conflict["pattern1"], conflict["pattern2"]],
                "description": "Resolve pattern conflict"
            })
        
        return recommendations
    
    def _calculate_conflict_severity(
        self,
        pattern1: Dict[str, Any],
        pattern2: Dict[str, Any]
    ) -> str:
        """Calculate the severity of a pattern conflict."""
        # Check for critical conflicts
        if (
            pattern1.get("type") == "security" or
            pattern2.get("type") == "security"
        ):
            return "high"
        
        # Check for major conflicts
        if (
            pattern1.get("type") == "architecture" or
            pattern2.get("type") == "architecture"
        ):
            return "medium"
        
        return "low"
    
    async def _update_learning_metrics(self, patterns: List[Dict[str, Any]]) -> None:
        """Update learning metrics."""
        self._learning_metrics.total_patterns_learned += len(patterns)
        self._learning_metrics.code_patterns_learned += len([p for p in patterns if p["type"] == "code"])
        self._learning_metrics.doc_patterns_learned += len([p for p in patterns if p["type"] == "doc"])
        self._learning_metrics.arch_patterns_learned += len([p for p in patterns if p["type"] == "arch"])
        self._learning_metrics.cross_repo_patterns += len([p for p in patterns if len(p.get("repositories", [])) > 1])
        self._learning_metrics.last_update = asyncio.get_event_loop().time()
    
    def _group_similar_patterns(
        self,
        patterns: List[Tuple[int, Dict[str, Any]]]
    ) -> List[List[Tuple[int, Dict[str, Any]]]]:
        """Group similar patterns together."""
        groups = []
        used_patterns = set()
        
        for i, (repo_id1, pattern1) in enumerate(patterns):
            if pattern1["id"] in used_patterns:
                continue
                
            current_group = [(repo_id1, pattern1)]
            used_patterns.add(pattern1["id"])
            
            for repo_id2, pattern2 in patterns[i + 1:]:
                if pattern2["id"] in used_patterns:
                    continue
                    
                if self._ai_processor._calculate_pattern_similarity(pattern1, pattern2) > 0.8:
                    current_group.append((repo_id2, pattern2))
                    used_patterns.add(pattern2["id"])
            
            if current_group:
                groups.append(current_group)
        
        return groups
    
    def _create_common_pattern(
        self,
        pattern_group: List[Tuple[int, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Create a common pattern from a group of similar patterns."""
        # Use the pattern with highest confidence as base
        base_pattern = max(pattern_group, key=lambda x: x[1].get("confidence", 0))[1]
        
        # Combine repositories
        repositories = [repo_id for repo_id, _ in pattern_group]
        
        # Calculate average confidence
        avg_confidence = sum(p.get("confidence", 0) for _, p in pattern_group) / len(pattern_group)
        
        return {
            "id": f"common_{base_pattern['id']}",
            "name": base_pattern["name"],
            "type": base_pattern["type"],
            "content": base_pattern["content"],
            "confidence": avg_confidence,
            "repositories": repositories,
            "frequency": len(repositories),
            "metadata": {
                "source_patterns": [p["id"] for _, p in pattern_group],
                "created_at": asyncio.get_event_loop().time()
            }
        }

    @handle_async_errors(error_types=(ProcessingError,))
    async def _enhance_results(
        self,
        pattern_results: Dict[str, Any],
        code_context: Dict[str, Any],
        graph_insights: Dict[str, Any],
        learned_patterns: List[Dict[str, Any]],
        context: AIAssistantContext
    ) -> Dict[str, Any]:
        """Enhance pattern results with AI tool insights."""
        enhanced = pattern_results.copy()
        
        # Add code understanding insights
        if pattern_results.get("immediate_response"):
            task = asyncio.create_task(self.code_understanding.enhance_response(
                pattern_results["immediate_response"],
                code_context
            ))
            self._pending_tasks.add(task)
            try:
                enhanced["code_context"] = await task
            finally:
                self._pending_tasks.remove(task)
        
        # Add graph insights
        if graph_insights:
            task = asyncio.create_task(self.graph_capabilities.enhance_response(
                pattern_results,
                graph_insights
            ))
            self._pending_tasks.add(task)
            try:
                enhanced["dependencies"] = await task
            finally:
                self._pending_tasks.remove(task)
        
        # Add learned pattern insights
        if learned_patterns:
            task = asyncio.create_task(reference_learning.enhance_response(
                pattern_results,
                learned_patterns
            ))
            self._pending_tasks.add(task)
            try:
                enhanced["learned_insights"] = await task
            finally:
                self._pending_tasks.remove(task)
        
        # Apply rules
        task = asyncio.create_task(self.rule_config.apply_rules(
            pattern_results,
            context
        ))
        self._pending_tasks.add(task)
        try:
            enhanced["rule_based_suggestions"] = await task
        finally:
            self._pending_tasks.remove(task)
        
        # Add confidence levels
        enhanced["confidence_levels"] = self._calculate_confidence_levels(enhanced)
        
        return enhanced
    
    def _calculate_confidence_levels(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Calculate confidence levels for different aspects of the results."""
        confidence_levels = {
            "overall": results.get("confidence", 0.0),
            "code_understanding": 0.0,
            "dependencies": 0.0,
            "learned_patterns": 0.0,
            "rules": 0.0
        }
        
        # Calculate code understanding confidence
        if "code_context" in results:
            confidence_levels["code_understanding"] = self._calculate_context_confidence(
                results["code_context"]
            )
        
        # Calculate dependencies confidence
        if "dependencies" in results:
            confidence_levels["dependencies"] = self._calculate_dependency_confidence(
                results["dependencies"]
            )
        
        # Calculate learned patterns confidence
        if "learned_insights" in results:
            confidence_levels["learned_patterns"] = self._calculate_learning_confidence(
                results["learned_insights"]
            )
        
        # Calculate rules confidence
        if "rule_based_suggestions" in results:
            confidence_levels["rules"] = self._calculate_rules_confidence(
                results["rule_based_suggestions"]
            )
        
        return confidence_levels
    
    def _calculate_context_confidence(self, context: Dict[str, Any]) -> float:
        """Calculate confidence in code understanding context."""
        confidence = 0.5  # Base confidence
        
        if "completeness" in context:
            confidence += context["completeness"] * 0.3
            
        if "relevance" in context:
            confidence += context["relevance"] * 0.2
            
        return min(confidence, 1.0)
    
    def _calculate_dependency_confidence(self, dependencies: Dict[str, Any]) -> float:
        """Calculate confidence in dependency analysis."""
        confidence = 0.5  # Base confidence
        
        if "completeness" in dependencies:
            confidence += dependencies["completeness"] * 0.3
            
        if "accuracy" in dependencies:
            confidence += dependencies["accuracy"] * 0.2
            
        return min(confidence, 1.0)
    
    def _calculate_learning_confidence(self, insights: Dict[str, Any]) -> float:
        """Calculate confidence in learned patterns."""
        confidence = 0.5  # Base confidence
        
        if "pattern_matches" in insights:
            confidence += len(insights["pattern_matches"]) * 0.1
            
        if "similarity_score" in insights:
            confidence += insights["similarity_score"] * 0.2
            
        return min(confidence, 1.0)
    
    def _calculate_rules_confidence(self, suggestions: Dict[str, Any]) -> float:
        """Calculate confidence in rule-based suggestions."""
        confidence = 0.5  # Base confidence
        
        if "matched_rules" in suggestions:
            confidence += len(suggestions["matched_rules"]) * 0.1
            
        if "rule_scores" in suggestions:
            avg_score = sum(suggestions["rule_scores"]) / len(suggestions["rule_scores"])
            confidence += avg_score * 0.2
            
        return min(confidence, 1.0)
    
    async def cleanup(self):
        """Clean up integration resources."""
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
            
            # Clean up components in reverse initialization order
            cleanup_tasks = []
            
            if self._ai_processor:
                task = asyncio.create_task(self._ai_processor.cleanup())
                cleanup_tasks.append(task)
            
            if self._pattern_processor:
                task = asyncio.create_task(self._pattern_processor.cleanup())
                cleanup_tasks.append(task)
            
            if self.rule_config:
                task = asyncio.create_task(self.rule_config.cleanup())
                cleanup_tasks.append(task)
            
            if self._pattern_storage:
                task = asyncio.create_task(self._pattern_storage.cleanup())
                cleanup_tasks.append(task)
            
            if self.graph_capabilities:
                task = asyncio.create_task(self.graph_capabilities.cleanup())
                cleanup_tasks.append(task)
            
            if self.code_understanding:
                task = asyncio.create_task(self.code_understanding.cleanup())
                cleanup_tasks.append(task)
            
            if self.ai_interface:
                task = asyncio.create_task(self.ai_interface.cleanup())
                cleanup_tasks.append(task)
            
            # Wait for all cleanup tasks
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("pattern_integration")
            
            self._initialized = False
            await log("Pattern integration cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern integration: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup pattern integration: {e}")

    async def _extract_reference_patterns(
        self,
        reference_repo_id: int
    ) -> List[Dict[str, Any]]:
        """Extract patterns from a reference repository."""
        patterns = []
        
        # Get repository structure
        structure = await self.graph_capabilities.get_repository_structure(reference_repo_id)
        
        # Extract code patterns
        code_patterns = await self._extract_code_patterns(reference_repo_id, structure)
        patterns.extend(code_patterns)
        
        # Extract documentation patterns
        doc_patterns = await self._extract_doc_patterns(reference_repo_id, structure)
        patterns.extend(doc_patterns)
        
        # Extract architecture patterns
        arch_patterns = await self._extract_arch_patterns(reference_repo_id, structure)
        patterns.extend(arch_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze extracted patterns."""
        analysis = {
            "pattern_types": {},
            "language_distribution": {},
            "complexity_metrics": {},
            "best_practices": [],
            "potential_issues": []
        }
        
        # Analyze pattern types
        for pattern in patterns:
            pattern_type = pattern.get("type")
            if pattern_type not in analysis["pattern_types"]:
                analysis["pattern_types"][pattern_type] = 0
            analysis["pattern_types"][pattern_type] += 1
        
        # Analyze language distribution
        for pattern in patterns:
            language = pattern.get("language")
            if language not in analysis["language_distribution"]:
                analysis["language_distribution"][language] = 0
            analysis["language_distribution"][language] += 1
        
        # Calculate complexity metrics
        analysis["complexity_metrics"] = await self._calculate_complexity_metrics(patterns)
        
        # Identify best practices
        analysis["best_practices"] = await self._identify_best_practices(patterns)
        
        # Identify potential issues
        analysis["potential_issues"] = await self._identify_potential_issues(patterns)
        
        return analysis

    async def _apply_patterns_to_target(
        self,
        patterns: List[Dict[str, Any]],
        target_repo_id: int
    ) -> Dict[str, Any]:
        """Apply patterns to a target repository."""
        results = {
            "applied_patterns": [],
            "skipped_patterns": [],
            "failed_patterns": [],
            "recommendations": []
        }
        
        # Get target repository structure
        target_structure = await self.graph_capabilities.get_repository_structure(target_repo_id)
        
        # Analyze target repository
        target_analysis = await self.code_understanding.analyze_codebase(target_repo_id)
        
        # Apply each pattern
        for pattern in patterns:
            try:
                # Check if pattern is applicable
                if await self._is_pattern_applicable(pattern, target_structure, target_analysis):
                    # Apply pattern
                    application_result = await self._apply_pattern(
                        pattern,
                        target_repo_id,
                        target_structure
                    )
                    
                    if application_result["success"]:
                        results["applied_patterns"].append({
                            "pattern": pattern,
                            "result": application_result
                        })
                    else:
                        results["failed_patterns"].append({
                            "pattern": pattern,
                            "error": application_result["error"]
                        })
                else:
                    results["skipped_patterns"].append({
                        "pattern": pattern,
                        "reason": "Not applicable to target repository"
                    })
            except Exception as e:
                results["failed_patterns"].append({
                    "pattern": pattern,
                    "error": str(e)
                })
        
        # Generate recommendations
        results["recommendations"] = await self._generate_recommendations(
            patterns,
            target_structure,
            target_analysis
        )
        
        return results

    async def _is_pattern_applicable(
        self,
        pattern: Dict[str, Any],
        target_structure: Dict[str, Any],
        target_analysis: Dict[str, Any]
    ) -> bool:
        """Check if a pattern is applicable to the target repository."""
        # Check language compatibility
        if pattern.get("language") not in target_analysis.get("languages", []):
            return False
        
        # Check structure compatibility
        required_structure = pattern.get("required_structure", {})
        if not self._check_structure_compatibility(required_structure, target_structure):
            return False
        
        # Check dependencies
        dependencies = pattern.get("dependencies", [])
        if not await self._check_dependencies(dependencies, target_structure):
            return False
        
        return True

    def _check_structure_compatibility(
        self,
        required: Dict[str, Any],
        target: Dict[str, Any]
    ) -> bool:
        """Check if required structure exists in target."""
        for key, value in required.items():
            if key not in target:
                return False
            if isinstance(value, dict):
                if not self._check_structure_compatibility(value, target[key]):
                    return False
            elif isinstance(value, list):
                if not all(item in target[key] for item in value):
                    return False
            elif value != target[key]:
                return False
        return True

    async def _check_dependencies(
        self,
        dependencies: List[str],
        target_structure: Dict[str, Any]
    ) -> bool:
        """Check if all dependencies are satisfied."""
        for dep in dependencies:
            if not await self._check_dependency(dep, target_structure):
                return False
        return True

    async def _check_dependency(
        self,
        dependency: str,
        target_structure: Dict[str, Any]
    ) -> bool:
        """Check if a specific dependency is satisfied."""
        # Check for required files
        if dependency.startswith("file:"):
            required_file = dependency[5:]
            return required_file in target_structure.get("files", [])
        
        # Check for required directories
        if dependency.startswith("dir:"):
            required_dir = dependency[4:]
            return required_dir in target_structure.get("directories", [])
        
        # Check for required patterns
        if dependency.startswith("pattern:"):
            required_pattern = dependency[8:]
            return required_pattern in target_structure.get("patterns", [])
        
        return False

    async def _apply_pattern(
        self,
        pattern: Dict[str, Any],
        target_repo_id: int,
        target_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a pattern to the target repository."""
        try:
            # Get pattern implementation
            implementation = await self._get_pattern_implementation(pattern)
            
            # Apply implementation
            result = await implementation.apply(
                target_repo_id,
                target_structure
            )
            
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_pattern_implementation(
        self,
        pattern: Dict[str, Any]
    ) -> Any:
        """Get the implementation for a pattern."""
        # This would typically load the appropriate implementation class
        # based on the pattern type and language
        pattern_type = pattern.get("type")
        language = pattern.get("language")
        
        # For now, return a mock implementation
        class MockImplementation:
            async def apply(self, repo_id, structure):
                return {"status": "applied"}
        
        return MockImplementation()

    async def _calculate_complexity_metrics(
        self,
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate complexity metrics for patterns."""
        metrics = {
            "average_complexity": 0.0,
            "complexity_distribution": {},
            "maintainability_score": 0.0,
            "reusability_score": 0.0
        }
        
        # Calculate average complexity
        complexities = [p.get("complexity", 0) for p in patterns]
        if complexities:
            metrics["average_complexity"] = sum(complexities) / len(complexities)
        
        # Calculate complexity distribution
        for complexity in complexities:
            if complexity not in metrics["complexity_distribution"]:
                metrics["complexity_distribution"][complexity] = 0
            metrics["complexity_distribution"][complexity] += 1
        
        # Calculate maintainability score
        metrics["maintainability_score"] = self._calculate_maintainability_score(patterns)
        
        # Calculate reusability score
        metrics["reusability_score"] = self._calculate_reusability_score(patterns)
        
        return metrics

    def _calculate_maintainability_score(
        self,
        patterns: List[Dict[str, Any]]
    ) -> float:
        """Calculate maintainability score for patterns."""
        if not patterns:
            return 0.0
        
        # Consider factors like complexity, dependencies, and documentation
        scores = []
        for pattern in patterns:
            score = 0.0
            
            # Complexity factor (lower is better)
            complexity = pattern.get("complexity", 0)
            score += (1.0 - min(complexity / 10, 1.0)) * 0.4
            
            # Dependencies factor (fewer is better)
            dependencies = len(pattern.get("dependencies", []))
            score += (1.0 - min(dependencies / 5, 1.0)) * 0.3
            
            # Documentation factor
            has_docs = bool(pattern.get("documentation"))
            score += (1.0 if has_docs else 0.0) * 0.3
            
            scores.append(score)
        
        return sum(scores) / len(scores)

    def _calculate_reusability_score(
        self,
        patterns: List[Dict[str, Any]]
    ) -> float:
        """Calculate reusability score for patterns."""
        if not patterns:
            return 0.0
        
        # Consider factors like generality, dependencies, and interface
        scores = []
        for pattern in patterns:
            score = 0.0
            
            # Generality factor
            generality = pattern.get("generality", 0.5)
            score += generality * 0.4
            
            # Dependencies factor (fewer is better)
            dependencies = len(pattern.get("dependencies", []))
            score += (1.0 - min(dependencies / 5, 1.0)) * 0.3
            
            # Interface factor
            has_interface = bool(pattern.get("interface"))
            score += (1.0 if has_interface else 0.0) * 0.3
            
            scores.append(score)
        
        return sum(scores) / len(scores)

    async def _identify_potential_issues(
        self,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify potential issues in patterns."""
        issues = []
        
        for pattern in patterns:
            # Check complexity
            if pattern.get("complexity", 0) > 8:
                issues.append({
                    "pattern": pattern,
                    "type": "high_complexity",
                    "severity": "warning",
                    "description": "Pattern has high complexity"
                })
            
            # Check dependencies
            if len(pattern.get("dependencies", [])) > 5:
                issues.append({
                    "pattern": pattern,
                    "type": "many_dependencies",
                    "severity": "warning",
                    "description": "Pattern has many dependencies"
                })
            
            # Check documentation
            if not pattern.get("documentation"):
                issues.append({
                    "pattern": pattern,
                    "type": "missing_documentation",
                    "severity": "info",
                    "description": "Pattern lacks documentation"
                })
            
            # Check maintainability
            maintainability = self._calculate_maintainability_score([pattern])
            if maintainability < 0.5:
                issues.append({
                    "pattern": pattern,
                    "type": "low_maintainability",
                    "severity": "warning",
                    "description": "Pattern has low maintainability"
                })
        
        return issues

    async def _generate_recommendations(
        self,
        patterns: List[Dict[str, Any]],
        target_structure: Dict[str, Any],
        target_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on patterns and target repository."""
        recommendations = []
        
        # Analyze target repository
        target_metrics = await self._calculate_complexity_metrics(patterns)
        
        # Generate recommendations based on metrics
        if target_metrics["average_complexity"] > 7:
            recommendations.append({
                "type": "complexity_reduction",
                "priority": "high",
                "description": "Consider breaking down complex patterns into smaller, more manageable ones"
            })
        
        if target_metrics["maintainability_score"] < 0.6:
            recommendations.append({
                "type": "maintainability_improvement",
                "priority": "medium",
                "description": "Add documentation and reduce dependencies to improve maintainability"
            })
        
        if target_metrics["reusability_score"] < 0.5:
            recommendations.append({
                "type": "reusability_improvement",
                "priority": "medium",
                "description": "Consider making patterns more generic and adding clear interfaces"
            })
        
        # Generate recommendations based on best practices
        best_practices = await self._identify_best_practices(patterns)
        for practice in best_practices:
            recommendations.append({
                "type": "best_practice",
                "priority": "high",
                "description": f"Consider adopting {practice['type']} patterns from best practices"
            })
        
        return recommendations

# Create global instance
pattern_integration = None

async def get_pattern_integration() -> PatternIntegration:
    """Get the global pattern integration instance."""
    global pattern_integration
    if not pattern_integration:
        pattern_integration = await PatternIntegration.create()
    return pattern_integration 