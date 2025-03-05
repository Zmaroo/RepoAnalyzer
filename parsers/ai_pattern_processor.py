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
    """AI-specific pattern processing system."""
    
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
                AICapability.DEEP_LEARNING  # Added deep learning capability
            }
        )
        self.base_processor = base_processor
        self._pattern_memory: Dict[str, float] = {}
        self._interaction_history: List[Dict[str, Any]] = []
        self._pattern_integration = None
        self._deep_learning_cache: Dict[str, Dict[str, Any]] = {}  # Cache for deep learning results
        self._cross_repo_patterns: Dict[str, List[Dict[str, Any]]] = {}  # Store cross-repo patterns
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._pattern_cache = {}
        self._capabilities = {
            "deep_learning": True,
            "pattern_learning": True,
            "code_generation": True,
            "cross_repo_analysis": True
        }
        self._deep_learning_results = {}
        self._pattern_learning_cache = {}
    
    async def initialize(self):
        """Initialize the processor."""
        if not self._initialized:
            try:
                # Initialize embedders
                await code_embedder.initialize()
                await doc_embedder.initialize()
                await arch_embedder.initialize()
                
                self._initialized = True
                log("AI pattern processor initialized", level="info")
            except Exception as e:
                log(f"Error initializing AI pattern processor: {e}", level="error")
                raise
    
    async def initialize_integration(self, pattern_integration):
        """Initialize pattern integration layer."""
        self._pattern_integration = pattern_integration
        await self._pattern_integration.initialize(self.base_processor)
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process an interaction with full context awareness."""
        if self._pattern_integration:
            # Use pattern integration layer if available
            return await self._pattern_integration.process_interaction(source_code, context)
        
        # Get relevant patterns based on interaction type
        patterns = await self._get_relevant_patterns(source_code, context)
        
        # Process patterns with context
        results = await self._process_patterns_with_context(patterns, context)
        
        # Update interaction history
        self._update_history(patterns, results)
        
        return results
    
    async def _get_relevant_patterns(
        self,
        source_code: str,
        context: AIContext
    ) -> List[ProcessedPattern]:
        """Get patterns relevant to the current interaction."""
        interaction_type = context.interaction.interaction_type
        
        # Map interaction types to pattern purposes and categories
        purpose_map = {
            InteractionType.QUESTION: (PatternPurpose.EXPLANATION, [PatternCategory.CONTEXT, PatternCategory.SEMANTICS]),
            InteractionType.MODIFICATION: (PatternPurpose.MODIFICATION, [PatternCategory.SYNTAX, PatternCategory.CODE_PATTERNS]),
            InteractionType.ERROR: (PatternPurpose.DEBUGGING, [PatternCategory.COMMON_ISSUES, PatternCategory.SYNTAX]),
            InteractionType.COMPLETION: (PatternPurpose.COMPLETION, [PatternCategory.USER_PATTERNS, PatternCategory.CODE_PATTERNS]),
            InteractionType.EXPLANATION: (PatternPurpose.EXPLANATION, [PatternCategory.CONTEXT, PatternCategory.DOCUMENTATION]),
            InteractionType.SUGGESTION: (PatternPurpose.SUGGESTION, [PatternCategory.BEST_PRACTICES, PatternCategory.USER_PATTERNS]),
            InteractionType.DOCUMENTATION: (PatternPurpose.DOCUMENTATION, [PatternCategory.DOCUMENTATION, PatternCategory.CONTEXT])
        }
        
        purpose, categories = purpose_map[interaction_type]
        return await self.base_processor.process_for_purpose(
            source_code,
            purpose,
            context.project.file_type,
            categories
        )
    
    async def _process_patterns_with_context(
        self,
        patterns: List[ProcessedPattern],
        context: AIContext
    ) -> AIProcessingResult:
        """Process patterns considering all context."""
        results = AIProcessingResult(
            success=True,
            response=None,
            suggestions=[],
            context_info={},
            confidence=0.0,
            learned_patterns=[],
            ai_insights={}
        )
        
        # Process each pattern with context
        for pattern in patterns:
            # Calculate confidence using multiple metrics
            pattern_confidence = await self._calculate_confidence(pattern, context)
            
            # Add AI-specific insights
            ai_insights = await self._get_ai_insights(pattern, context)
            if ai_insights:
                results.ai_insights[pattern.pattern_name] = ai_insights
            
            # Store results based on confidence
            if pattern_confidence >= 0.8:  # HIGH confidence
                results.response = self._generate_response(pattern, context)
                results.confidence = pattern_confidence
            elif pattern_confidence >= 0.5:  # MEDIUM confidence
                results.suggestions.append(self._generate_suggestion(pattern, context))
            elif pattern_confidence >= 0.2:  # LOW confidence
                results.context_info.update(self._extract_context(pattern))
            
            # Learn from pattern
            learned = await self._learn_from_pattern(pattern, pattern_confidence)
            if learned:
                results.learned_patterns.append(learned)
        
        return results
    
    async def _calculate_confidence(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate overall confidence using multiple metrics."""
        metrics = {}
        
        # Pattern match confidence
        metrics[AIConfidenceMetrics.PATTERN_MATCH] = pattern.confidence
        
        # Context relevance
        metrics[AIConfidenceMetrics.CONTEXT_RELEVANCE] = await self._calculate_context_relevance(pattern, context)
        
        # User history confidence
        metrics[AIConfidenceMetrics.USER_HISTORY] = await self._calculate_user_history_confidence(pattern, context)
        
        # Project relevance
        metrics[AIConfidenceMetrics.PROJECT_RELEVANCE] = await self._calculate_project_relevance(pattern, context)
        
        # Language support confidence
        metrics[AIConfidenceMetrics.LANGUAGE_SUPPORT] = await self._calculate_language_support_confidence(pattern, context)
        
        # Update context with metrics
        context.confidence_metrics.update(metrics)
        
        # Calculate weighted average
        weights = {
            AIConfidenceMetrics.PATTERN_MATCH: 0.3,
            AIConfidenceMetrics.CONTEXT_RELEVANCE: 0.25,
            AIConfidenceMetrics.USER_HISTORY: 0.2,
            AIConfidenceMetrics.PROJECT_RELEVANCE: 0.15,
            AIConfidenceMetrics.LANGUAGE_SUPPORT: 0.1
        }
        
        confidence = sum(metrics[m] * weights[m] for m in metrics)
        return min(confidence, 1.0)

    async def _calculate_context_relevance(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate how relevant a pattern is to the current context."""
        relevance = 0.5  # Base relevance
        
        # Check interaction type relevance
        if pattern.purpose == context.interaction.interaction_type:
            relevance += 0.2
        
        # Check user context relevance
        if pattern.pattern_name in context.user.preferred_style:
            relevance += 0.2
        
        # Check project context relevance
        if pattern.pattern_name in context.project.project_patterns:
            relevance += 0.1
        
        return min(relevance, 1.0)
    
    async def _calculate_user_history_confidence(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate confidence based on user interaction history."""
        confidence = 0.5  # Base confidence
        
        # Check recent interactions
        recent_uses = sum(
            1 for interaction in context.user.recent_interactions[-5:]
            if pattern.pattern_name in interaction.get("patterns_used", [])
        )
        confidence += (recent_uses * 0.1)
        
        # Check pattern memory
        if pattern.pattern_name in self._pattern_memory:
            historical_confidence = self._pattern_memory[pattern.pattern_name]
            confidence = (confidence + historical_confidence) / 2
        
        return min(confidence, 1.0)
    
    async def _calculate_project_relevance(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate how relevant a pattern is to the project."""
        relevance = 0.5  # Base relevance
        
        # Check project style guide
        if pattern.pattern_name in context.project.style_guide:
            relevance += 0.2
        
        # Check known issues
        if any(pattern.pattern_name in issue.get("related_patterns", [])
               for issue in context.project.known_issues):
            relevance += 0.15
        
        # Check project patterns
        if pattern.pattern_name in context.project.project_patterns:
            relevance += 0.15
        
        return min(relevance, 1.0)
    
    async def _calculate_language_support_confidence(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> float:
        """Calculate confidence based on language support."""
        confidence = 0.5  # Base confidence
        
        # Check if pattern is language-specific
        if hasattr(pattern, 'language_id') and pattern.language_id == context.project.language_id:
            confidence += 0.3
        
        # Check user's language skill level
        skill_level = context.user.skill_level.get(context.project.language_id, 0.5)
        if skill_level > 0.7:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _generate_response(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> str:
        """Generate a response based on a pattern."""
        interaction_type = context.interaction.interaction_type
        
        if interaction_type == InteractionType.QUESTION:
            return self._format_explanation(pattern)
        elif interaction_type == InteractionType.MODIFICATION:
            return self._format_modification(pattern)
        elif interaction_type == InteractionType.ERROR:
            return self._format_error_solution(pattern)
        elif interaction_type == InteractionType.COMPLETION:
            return self._format_completion(pattern)
        elif interaction_type == InteractionType.EXPLANATION:
            return self._format_detailed_explanation(pattern)
        elif interaction_type == InteractionType.SUGGESTION:
            return self._format_suggestion(pattern)
        else:
            return self._format_documentation(pattern)
    
    def _generate_suggestion(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> str:
        """Generate a suggestion based on a pattern."""
        return f"Suggested {pattern.category.value}: {pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _extract_context(self, pattern: ProcessedPattern) -> Dict[str, Any]:
        """Extract relevant context information from a pattern."""
        return {
            "category": pattern.category.value,
            "purpose": pattern.purpose.value,
            "related_patterns": self._find_related_patterns(pattern),
            "metadata": pattern.metadata
        }
    
    async def _learn_from_pattern(
        self,
        pattern: ProcessedPattern,
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """Learn from a pattern and its usage."""
        if pattern.pattern_name not in self._pattern_memory:
            # New pattern discovered
            self._pattern_memory[pattern.pattern_name] = confidence
            return {
                "pattern_name": pattern.pattern_name,
                "category": pattern.category.value,
                "purpose": pattern.purpose.value,
                "initial_confidence": confidence,
                "context": self._extract_context(pattern)
            }
        else:
            # Update existing pattern confidence
            old_confidence = self._pattern_memory[pattern.pattern_name]
            new_confidence = (old_confidence * 0.8) + (confidence * 0.2)
            self._pattern_memory[pattern.pattern_name] = new_confidence
            return None
    
    def _update_history(
        self,
        patterns: List[ProcessedPattern],
        results: AIProcessingResult
    ) -> None:
        """Update interaction history."""
        self._interaction_history.append({
            "patterns_used": [p.pattern_name for p in patterns],
            "confidence": results.confidence,
            "successful_patterns": [
                p.pattern_name for p in patterns
                if p.confidence >= 0.8
            ],
            "learned_patterns": [
                p["pattern_name"] for p in results.learned_patterns
            ]
        })
        
        # Keep history manageable
        if len(self._interaction_history) > 100:
            self._interaction_history = self._interaction_history[-100:]
    
    async def _get_ai_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get AI-specific insights for a pattern."""
        insights = {}
        
        # Add capability-specific insights
        if AICapability.CODE_UNDERSTANDING in context.capabilities:
            insights["understanding"] = await self._get_understanding_insights(pattern, context)
        
        if AICapability.CODE_GENERATION in context.capabilities:
            insights["generation"] = await self._get_generation_insights(pattern, context)
            
        if AICapability.CODE_MODIFICATION in context.capabilities:
            insights["modification"] = await self._get_modification_insights(pattern, context)
            
        if AICapability.CODE_REVIEW in context.capabilities:
            insights["review"] = await self._get_review_insights(pattern, context)
            
        if AICapability.DOCUMENTATION in context.capabilities:
            insights["documentation"] = await self._get_documentation_insights(pattern, context)
            
        if AICapability.LEARNING in context.capabilities:
            insights["learning"] = await self._get_learning_insights(pattern, context)
        
        return insights
    
    async def _get_understanding_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get code understanding insights."""
        return {
            "complexity": self._analyze_complexity(pattern),
            "dependencies": self._analyze_dependencies(pattern),
            "context_relevance": self._analyze_context_relevance(pattern, context)
        }
    
    async def _get_generation_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get code generation insights."""
        return {
            "generation_confidence": self._calculate_generation_confidence(pattern),
            "suggested_templates": self._get_suggested_templates(pattern),
            "style_compatibility": self._check_style_compatibility(pattern, context)
        }
    
    async def _get_modification_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get code modification insights."""
        return {
            "modification_impact": self._analyze_modification_impact(pattern),
            "safety_score": self._calculate_safety_score(pattern),
            "suggested_changes": self._get_suggested_changes(pattern)
        }
    
    async def _get_review_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get code review insights."""
        return {
            "quality_score": self._calculate_quality_score(pattern),
            "improvement_suggestions": self._get_improvement_suggestions(pattern),
            "best_practices_alignment": self._check_best_practices(pattern)
        }
    
    async def _get_documentation_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get documentation insights."""
        return {
            "documentation_quality": self._analyze_documentation_quality(pattern),
            "missing_docs": self._find_missing_documentation(pattern),
            "doc_suggestions": self._get_documentation_suggestions(pattern)
        }
    
    async def _get_learning_insights(
        self,
        pattern: ProcessedPattern,
        context: AIContext
    ) -> Dict[str, Any]:
        """Get learning insights."""
        return {
            "learning_value": self._calculate_learning_value(pattern),
            "pattern_frequency": self._analyze_pattern_frequency(pattern),
            "knowledge_gaps": self._identify_knowledge_gaps(pattern, context)
        }

    def _format_explanation(self, pattern: ProcessedPattern) -> str:
        """Format pattern for answering questions."""
        return f"Based on the {pattern.category.value} pattern '{pattern.pattern_name}', " + \
               f"here's what I found: {pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_modification(self, pattern: ProcessedPattern) -> str:
        """Format pattern for code modifications."""
        return f"Suggested modification based on {pattern.pattern_name}: " + \
               f"{pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_error_solution(self, pattern: ProcessedPattern) -> str:
        """Format pattern for error solutions."""
        return f"Potential solution based on {pattern.pattern_name}: " + \
               f"{pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_completion(self, pattern: ProcessedPattern) -> str:
        """Format pattern for code completion."""
        return f"Completion suggestion: {pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_detailed_explanation(self, pattern: ProcessedPattern) -> str:
        """Format pattern for detailed explanations."""
        return f"Detailed explanation of {pattern.pattern_name}:\n" + \
               f"{pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_suggestion(self, pattern: ProcessedPattern) -> str:
        """Format pattern for suggestions."""
        return f"Suggestion based on {pattern.category.value} pattern: " + \
               f"{pattern.matches[0]['text'] if pattern.matches else ''}"
    
    def _format_documentation(self, pattern: ProcessedPattern) -> str:
        """Format pattern for documentation."""
        return f"Documentation for {pattern.pattern_name}:\n" + \
               f"{pattern.matches[0]['text'] if pattern.matches else ''}"

    def _find_related_patterns(self, pattern: ProcessedPattern) -> List[str]:
        """Find patterns related to the given pattern."""
        related = []
        for other_pattern in self._pattern_memory:
            if other_pattern != pattern.pattern_name:
                if (other_pattern in self.context.project.project_patterns and
                    pattern.pattern_name in self.context.project.project_patterns):
                    related.append(other_pattern)
                elif (other_pattern in self.context.user.common_patterns and
                      pattern.pattern_name in self.context.user.common_patterns):
                    related.append(other_pattern)
        return related

    async def deep_learn_from_multiple_repositories(
        self,
        repo_ids: List[int],
        pattern_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Perform deep learning analysis across multiple repositories."""
        if len(repo_ids) < 2:
            raise ValueError("Deep learning requires at least 2 repositories")
        
        results = {
            "common_patterns": [],
            "pattern_relationships": [],
            "cross_repo_insights": [],
            "recommendations": []
        }
        
        # Extract patterns from each repository
        repo_patterns = {}
        for repo_id in repo_ids:
            patterns = await self._extract_patterns_from_repo(repo_id, pattern_types)
            repo_patterns[repo_id] = patterns
        
        # Find common patterns across repositories
        common_patterns = await self._find_common_patterns(repo_patterns)
        results["common_patterns"] = common_patterns
        
        # Analyze relationships between patterns
        relationships = await self._analyze_pattern_relationships(common_patterns)
        results["pattern_relationships"] = relationships
        
        # Generate cross-repository insights
        insights = await self._generate_cross_repo_insights(
            repo_patterns,
            common_patterns,
            relationships
        )
        results["cross_repo_insights"] = insights
        
        # Cache results for future use
        cache_key = f"deep_learning:{'_'.join(map(str, repo_ids))}"
        self._deep_learning_results[cache_key] = results
        
        return results
    
    async def _extract_patterns_from_repo(
        self,
        repo_id: int,
        pattern_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract patterns from a repository."""
        patterns = []
        
        async with transaction_scope() as txn:
            # Query patterns from database
            query = """
            SELECT p.*, m.* 
            FROM patterns p
            LEFT JOIN pattern_metrics m ON p.id = m.pattern_id
            WHERE p.repo_id = :repo_id
            """
            if pattern_types:
                query += " AND p.pattern_type = ANY(:pattern_types)"
            
            results = await txn.execute(query, {
                "repo_id": repo_id,
                "pattern_types": pattern_types
            })
            
            for row in results:
                pattern = {
                    "id": row["id"],
                    "type": row["pattern_type"],
                    "content": row["content"],
                    "metrics": {
                        "complexity": row["complexity_score"],
                        "maintainability": row["maintainability_score"],
                        "reusability": row["reusability_score"]
                    }
                }
                patterns.append(pattern)
        
        return patterns
    
    async def _find_common_patterns(
        self,
        repo_patterns: Dict[int, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Find common patterns across repositories."""
        common_patterns = []
        
        # Get all patterns
        all_patterns = []
        for patterns in repo_patterns.values():
            all_patterns.extend(patterns)
        
        # Group similar patterns
        while all_patterns:
            pattern = all_patterns.pop(0)
            similar_patterns = []
            
            # Find similar patterns
            for other in all_patterns[:]:
                similarity = await self._calculate_pattern_similarity(pattern, other)
                if similarity > 0.8:  # High similarity threshold
                    similar_patterns.append(other)
                    all_patterns.remove(other)
            
            if similar_patterns:
                # Create common pattern group
                common_pattern = {
                    "base_pattern": pattern,
                    "similar_patterns": similar_patterns,
                    "repositories": list(set(p.get("repo_id") for p in [pattern] + similar_patterns)),
                    "confidence": await self._calculate_pattern_confidence(pattern, similar_patterns)
                }
                common_patterns.append(common_pattern)
        
        return common_patterns
    
    async def _analyze_pattern_relationships(
        self,
        common_patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze relationships between patterns."""
        relationships = []
        
        for i, pattern1 in enumerate(common_patterns):
            for pattern2 in common_patterns[i+1:]:
                # Calculate dependency strength
                dependency = await self._calculate_dependency_strength(
                    pattern1["base_pattern"],
                    pattern2["base_pattern"]
                )
                
                if dependency > 0.3:  # Significant dependency threshold
                    relationship = {
                        "source_pattern": pattern1["base_pattern"]["id"],
                        "target_pattern": pattern2["base_pattern"]["id"],
                        "type": "dependency",
                        "strength": dependency,
                        "metrics": await self._calculate_relationship_metrics(
                            pattern1,
                            pattern2,
                            dependency
                        )
                    }
                    relationships.append(relationship)
                
                # Calculate similarity
                similarity = await self._calculate_pattern_similarity(
                    pattern1["base_pattern"],
                    pattern2["base_pattern"]
                )
                
                if similarity > 0.6:  # Moderate similarity threshold
                    relationship = {
                        "source_pattern": pattern1["base_pattern"]["id"],
                        "target_pattern": pattern2["base_pattern"]["id"],
                        "type": "similarity",
                        "strength": similarity,
                        "metrics": await self._calculate_relationship_metrics(
                            pattern1,
                            pattern2,
                            similarity
                        )
                    }
                    relationships.append(relationship)
                
                # Check for conflicts
                conflicts = await self._check_pattern_conflicts(
                    pattern1["base_pattern"],
                    pattern2["base_pattern"]
                )
                
                if conflicts:
                    relationship = {
                        "source_pattern": pattern1["base_pattern"]["id"],
                        "target_pattern": pattern2["base_pattern"]["id"],
                        "type": "conflict",
                        "conflicts": conflicts,
                        "severity": await self._calculate_conflict_severity(conflicts)
                    }
                    relationships.append(relationship)
        
        return relationships
    
    async def _generate_cross_repo_insights(
        self,
        repo_patterns: Dict[int, List[Dict[str, Any]]],
        common_patterns: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate insights from cross-repository analysis."""
        insights = []
        
        # Analyze pattern distribution
        pattern_dist = await self._analyze_pattern_distribution(repo_patterns)
        insights.append({
            "type": "pattern_distribution",
            "data": pattern_dist,
            "recommendations": await self._generate_distribution_recommendations(pattern_dist)
        })
        
        # Analyze pattern evolution
        evolution = await self._analyze_pattern_evolution(common_patterns)
        insights.append({
            "type": "pattern_evolution",
            "data": evolution,
            "recommendations": await self._generate_evolution_recommendations(evolution)
        })
        
        # Analyze relationship patterns
        rel_patterns = await self._analyze_relationship_patterns(relationships)
        insights.append({
            "type": "relationship_patterns",
            "data": rel_patterns,
            "recommendations": await self._generate_relationship_recommendations(rel_patterns)
        })
        
        return insights
    
    async def _calculate_pattern_similarity(
        self,
        pattern1: Dict[str, Any],
        pattern2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two patterns."""
        # Generate embeddings
        embedding1 = await code_embedder.embed_pattern(pattern1)
        embedding2 = await code_embedder.embed_pattern(pattern2)
        
        # Calculate cosine similarity
        import numpy as np
        return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    
    async def _calculate_pattern_confidence(
        self,
        base_pattern: Dict[str, Any],
        similar_patterns: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for a common pattern."""
        # Base confidence from number of occurrences
        confidence = min(len(similar_patterns) / 5.0, 1.0)
        
        # Adjust based on pattern metrics
        if base_pattern.get("metrics"):
            metrics = base_pattern["metrics"]
            confidence *= (
                metrics.get("maintainability", 0.5) +
                metrics.get("reusability", 0.5)
            ) / 2.0
        
        return confidence
    
    async def _calculate_dependency_strength(
        self,
        pattern1: Dict[str, Any],
        pattern2: Dict[str, Any]
    ) -> float:
        """Calculate dependency strength between patterns."""
        # This is a placeholder - actual implementation would analyze code dependencies
        return 0.5
    
    async def _calculate_relationship_metrics(
        self,
        pattern1: Dict[str, Any],
        pattern2: Dict[str, Any],
        strength: float
    ) -> Dict[str, Any]:
        """Calculate metrics for pattern relationship."""
        return {
            "strength": strength,
            "confidence": min(
                pattern1.get("confidence", 0.5),
                pattern2.get("confidence", 0.5)
            ),
            "impact": strength * (
                pattern1.get("metrics", {}).get("complexity", 0.5) +
                pattern2.get("metrics", {}).get("complexity", 0.5)
            ) / 2.0
        }
    
    async def _check_pattern_conflicts(
        self,
        pattern1: Dict[str, Any],
        pattern2: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for conflicts between patterns."""
        # This is a placeholder - actual implementation would analyze potential conflicts
        return []
    
    async def _calculate_conflict_severity(
        self,
        conflicts: List[Dict[str, Any]]
    ) -> float:
        """Calculate severity of pattern conflicts."""
        if not conflicts:
            return 0.0
        return sum(c.get("severity", 0.5) for c in conflicts) / len(conflicts)
    
    async def cleanup(self):
        """Clean up processor resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear caches
            self._pattern_cache.clear()
            self._deep_learning_results.clear()
            self._pattern_learning_cache.clear()
            
            self._initialized = False
            log("AI pattern processor cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up AI pattern processor: {e}", level="error")

# Create global instance
processor = AIPatternProcessor()

# Export with proper async handling
async def get_processor() -> AIPatternProcessor:
    """Get the AI pattern processor instance.
    
    Returns:
        AIPatternProcessor: The singleton AI pattern processor instance
    """
    if not processor._initialized:
        await processor.initialize()
    return processor 