"""C++-specific patterns with enhanced type system and relationships.

This module provides C++-specific patterns that integrate with the enhanced
pattern processing system, including proper typing, relationships, and context.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# C++ capabilities
CPP_CAPABILITIES = {
    AICapability.CODE_UNDERSTANDING,
    AICapability.CODE_GENERATION,
    AICapability.CODE_MODIFICATION,
    AICapability.CODE_REVIEW,
    AICapability.LEARNING
}

# Pattern relationships for C++
CPP_PATTERN_RELATIONSHIPS = {
    "function": [
        PatternRelationship(
            source_pattern="function",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"return_type": True}
        ),
        PatternRelationship(
            source_pattern="function",
            target_pattern="comment",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "class": [
        PatternRelationship(
            source_pattern="class",
            target_pattern="function",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"methods": True}
        ),
        PatternRelationship(
            source_pattern="class",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.9,
            metadata={"member_types": True}
        )
    ],
    "template": [
        PatternRelationship(
            source_pattern="template",
            target_pattern="type",
            relationship_type=PatternRelationType.USES,
            confidence=0.95,
            metadata={"template_params": True}
        )
    ]
}

# Performance metrics tracking for C++ patterns
CPP_PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "class": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "template": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced C++ patterns with proper typing and relationships
CPP_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                name="function",
                pattern="""
                (function_definition
                    type: (_) @syntax.function.return_type
                    declarator: (function_declarator
                        declarator: (_) @syntax.function.name
                        parameters: (parameter_list) @syntax.function.params)
                    body: (compound_statement) @syntax.function.body) @syntax.function.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.95,
                metadata={
                    "relationships": CPP_PATTERN_RELATIONSHIPS["function"],
                    "metrics": CPP_PATTERN_METRICS["function"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    ),
                    "learning_enabled": True
                }
            ),
            
            "class": ResilientPattern(
                name="class",
                pattern="""
                (class_specifier
                    name: (type_identifier) @syntax.class.name
                    base_class_clause: (base_class_clause)? @syntax.class.bases
                    body: (field_declaration_list) @syntax.class.body) @syntax.class.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.95,
                metadata={
                    "relationships": CPP_PATTERN_RELATIONSHIPS["class"],
                    "metrics": CPP_PATTERN_METRICS["class"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "template": ResilientPattern(
                name="template",
                pattern="""
                (template_declaration
                    parameters: (template_parameter_list) @syntax.template.params
                    declaration: (_) @syntax.template.declaration) @syntax.template.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.95,
                metadata={
                    "relationships": CPP_PATTERN_RELATIONSHIPS["template"],
                    "metrics": CPP_PATTERN_METRICS["template"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "class_methods": AdaptivePattern(
                name="class_methods",
                pattern="""
                (class_specifier
                    body: (field_declaration_list 
                        (function_definition) @syntax.class.method)) @syntax.class.def
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.9,
                metadata={
                    "relationships": CPP_PATTERN_RELATIONSHIPS["class"],
                    "metrics": CPP_PATTERN_METRICS["class"],
                    "learning_context": {
                        "adapts_to": ["method_style", "naming_conventions"],
                        "learns_from": ["project_patterns", "code_style"]
                    }
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "type": AdaptivePattern(
                name="type",
                pattern="""
                [
                    (type_annotation
                        name: (_) @semantics.type.name
                        expression: (_) @semantics.type.expr) @semantics.type.def,
                    (type_variable
                        name: (lower_case_identifier) @semantics.type.var) @semantics.type.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "variable": AdaptivePattern(
                name="variable",
                pattern="""
                [
                    (declaration
                        type: (_) @semantics.variable.type
                        declarator: (identifier) @semantics.variable.name
                        default_value: (_)? @semantics.variable.value) @semantics.variable.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.9,
                metadata={
                    "relationships": [],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comments": AdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment,
                    (block_comment) @documentation.comment.block
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="cpp",
                confidence=0.9,
                metadata={
                    "relationships": [
                        PatternRelationship(
                            source_pattern="comments",
                            target_pattern="function",
                            relationship_type=PatternRelationType.COMPLEMENTS,
                            confidence=0.8
                        )
                    ],
                    "metrics": PatternPerformanceMetrics(),
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    }
}

cpp_pattern_learner = CrossProjectPatternLearner()

@handle_async_errors(error_types=ProcessingError)
async def learn_cpp_patterns(project_paths: List[str]) -> Dict[str, Any]:
    """Learn C++ patterns from multiple projects."""
    async with AsyncErrorBoundary(
        operation_name="cpp_pattern_learning",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        learned_patterns = {}
        
        for project_path in project_paths:
            patterns = await cpp_pattern_learner.learn_from_project(project_path)
            for pattern in patterns:
                pattern_key = f"{pattern['name']}_{pattern['category']}"
                if pattern_key not in learned_patterns:
                    learned_patterns[pattern_key] = pattern
                else:
                    # Merge pattern insights
                    learned_patterns[pattern_key]["confidence"] = max(
                        learned_patterns[pattern_key]["confidence"],
                        pattern["confidence"]
                    )
                    learned_patterns[pattern_key]["metadata"]["projects"].append(project_path)
        
        return learned_patterns

async def create_cpp_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create pattern context with full system integration."""
    # Get unified parser
    unified_parser = await get_unified_parser()
    
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="cpp",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "cpp"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(CPP_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def get_cpp_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return CPP_PATTERN_RELATIONSHIPS.get(pattern_name, [])

async def update_cpp_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics with logging."""
    try:
        if pattern_name in CPP_PATTERN_METRICS:
            pattern_metrics = CPP_PATTERN_METRICS[pattern_name]
            pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
            pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
            pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
            pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
            pattern_metrics.error_count = metrics.get("error_count", 0)
            
            total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
            if total > 0:
                pattern_metrics.success_rate = pattern_metrics.cache_hits / total
            
            await log(
                f"Updated metrics for pattern {pattern_name}",
                level="info",
                context={
                    "pattern": pattern_name,
                    "metrics": metrics,
                    "success_rate": pattern_metrics.success_rate
                }
            )
    except Exception as e:
        await log(f"Error updating pattern metrics: {e}", level="error")

def get_cpp_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_cpp_pattern_relationships(pattern_name),
        performance=CPP_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "cpp"}
    )

# Export public interfaces
__all__ = [
    'CPP_PATTERNS',
    'CPP_PATTERN_RELATIONSHIPS',
    'CPP_PATTERN_METRICS',
    'create_cpp_pattern_context',
    'get_cpp_pattern_relationships',
    'update_cpp_pattern_metrics',
    'get_cpp_pattern_match_result',
    'cpp_pattern_learner',
    'learn_cpp_patterns'
]

# Module identification
LANGUAGE = "cpp"

@cached_in_request(lambda pattern_name, source_code: f"cpp_pattern:{pattern_name}:{hash(source_code)}")
async def get_pattern_matches(pattern_name: str, source_code: str) -> List[Dict[str, Any]]:
    """Get pattern matches with request-level caching."""
    pattern = CPP_PATTERNS[pattern_name]
    return await pattern.matches(source_code)

@handle_async_errors(error_types=ProcessingError)
async def process_cpp_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a C++ pattern with full system integration."""
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("cpp", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "cpp", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_cpp_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "cpp",
            source_code,
            context.code_structure if context else None
        )
        
        # Process blocks and extract features
        matches = []
        start_time = time.time()
        
        for block in blocks:
            block_matches = await pattern.matches(block.content)
            if block_matches:
                # Extract features for each match
                for match in block_matches:
                    features = await feature_extractor.extract_features(
                        block.content,
                        match
                    )
                    match["features"] = features
                    match["block"] = block.__dict__
                matches.extend(block_matches)
        
        # Update pattern metrics
        await update_cpp_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

class CPPPatternLearner(CrossProjectPatternLearner):
    """Enhanced C++ pattern learner with full system integration."""
    
    def __init__(self):
        super().__init__()
        self._block_extractor = None
        self._feature_extractor = None
        self._unified_parser = None
        self._pattern_processor = pattern_processor
        self._ai_processor = None
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with all required components."""
        await super().initialize()
        
        # Initialize required components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("cpp", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register with pattern processor
        await self._pattern_processor.register_language_patterns(
            "cpp", 
            CPP_PATTERNS,
            self
        )

    async def _get_parser(self) -> BaseParser:
        """Get appropriate parser for C++."""
        # Try tree-sitter first
        tree_sitter_parser = await get_tree_sitter_parser("cpp")
        if tree_sitter_parser:
            return tree_sitter_parser
            
        # Fallback to base parser
        return await BaseParser.create(
            language_id="cpp",
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with AI assistance."""
        if not self._ai_processor:
            await self.initialize()
            
        # Try AI-assisted learning first
        ai_context = AIContext(
            language_id="cpp",
            file_type=FileType.CODE,
            interaction_type=InteractionType.LEARNING,
            repository_id=None,
            file_path=project_path
        )
        
        ai_result = await self._ai_processor.process_with_ai(
            source_code="",  # Will be filled by processor
            context=ai_context
        )
        
        if ai_result.success:
            return ai_result.learned_patterns
            
        # Fallback to standard learning
        async with AsyncErrorBoundary("cpp_pattern_learning"):
            # Extract blocks using block extractor
            blocks = await self._block_extractor.extract_from_project(
                project_path,
                language_id="cpp"
            )

            # Extract features from blocks
            features = []
            for block in blocks:
                block_features = await self._feature_extractor.extract_features(
                    block.content,
                    block.metadata
                )
                features.append(block_features)

            # Learn patterns from features
            patterns = await self._learn_patterns_from_features(features)
            
            return patterns

    async def _learn_patterns_from_features(
        self,
        features: List[ExtractedFeatures]
    ) -> List[Dict[str, Any]]:
        """Learn patterns from extracted features."""
        patterns = []
        
        # Group features by category
        for category in PatternCategory:
            category_features = [
                f for f in features 
                if f.category == category
            ]
            
            if category_features:
                # Learn patterns for this category
                learned = await self._learn_category_patterns(
                    category,
                    category_features
                )
                patterns.extend(learned)
        
        return patterns

    async def cleanup(self):
        """Clean up pattern learner resources."""
        if self._block_extractor:
            await self._block_extractor.cleanup()
        if self._feature_extractor:
            await self._feature_extractor.cleanup()
        if self._unified_parser:
            await self._unified_parser.cleanup()
        if self._ai_processor:
            await self._ai_processor.cleanup()

# Update initialization
async def initialize_cpp_patterns():
    """Initialize C++ patterns during app startup."""
    global cpp_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register C++ patterns
    await pattern_processor.register_language_patterns(
        "cpp",
        CPP_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": CPP_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    cpp_pattern_learner = await CPPPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "cpp",
        cpp_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "cpp_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(CPP_PATTERNS),
            "capabilities": list(CPP_CAPABILITIES)
        }
    )

async def extract_cpp_features(
    pattern: Union[AdaptivePattern, ResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    feature_extractor = await BaseFeatureExtractor.create("cpp", FileType.CODE)
    
    features = ExtractedFeatures()
    
    for match in matches:
        # Extract features based on pattern category
        if pattern.category == PatternCategory.SYNTAX:
            syntax_features = await feature_extractor._extract_syntax_features(
                match,
                context
            )
            features.update(syntax_features)
            
        elif pattern.category == PatternCategory.SEMANTICS:
            semantic_features = await feature_extractor._extract_semantic_features(
                match,
                context
            )
            features.update(semantic_features)
    
    return features 

async def validate_cpp_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a C++ pattern with system integration."""
    async with AsyncErrorBoundary("cpp_pattern_validation"):
        # Get pattern processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="cpp",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = CPP_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result 