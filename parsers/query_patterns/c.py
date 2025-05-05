"""C-specific patterns with enhanced type system and relationships.

This module provides C-specific patterns that integrate with the enhanced
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
from .common import (
    COMMON_PATTERNS, COMMON_CAPABILITIES,
    process_tree_sitter_pattern, validate_tree_sitter_pattern, create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern, 
    TreeSitterCrossProjectPatternLearner
)
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
import asyncio
from parsers.block_extractor import get_block_extractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
from parsers.feature_extractor import get_feature_extractor
import time

# C capabilities (extends common capabilities)
C_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.MEMORY_MANAGEMENT,
    AICapability.POINTER_ANALYSIS
}

# Pattern relationships for C
C_PATTERN_RELATIONSHIPS = {
    "function_definition": [
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="function_declaration",
            relationship_type=PatternRelationType.IMPLEMENTS,
            confidence=0.95,
            metadata={"implementation": True}
        ),
        PatternRelationship(
            source_pattern="function_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "struct_definition": [
        PatternRelationship(
            source_pattern="struct_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ],
    "enum_definition": [
        PatternRelationship(
            source_pattern="enum_definition",
            target_pattern="comments",
            relationship_type=PatternRelationType.COMPLEMENTS,
            confidence=0.8,
            metadata={"documentation": True}
        )
    ]
}

# Performance metrics tracking for C patterns
C_PATTERN_METRICS = {
    "function_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "struct_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    ),
    "enum_definition": PatternPerformanceMetrics(
        execution_time=0.0,
        memory_usage=0,
        cache_hits=0,
        cache_misses=0,
        error_count=0,
        success_rate=0.0,
        pattern_stats={"matches": 0, "failures": 0}
    )
}

# Enhanced C patterns with proper typing and relationships
C_PATTERNS = {
    **COMMON_PATTERNS,  # Inherit common patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            **COMMON_PATTERNS[PatternCategory.SYNTAX][PatternPurpose.UNDERSTANDING],  # Inherit common syntax patterns
            "function_definition": TreeSitterResilientPattern(
                name="function_definition",
                pattern="""
                [
                    (function_definition
                        declarator: (function_declarator
                            declarator: (identifier) @syntax.function.name
                            parameters: (parameter_list) @syntax.function.params)
                        type: (_) @syntax.function.return_type
                        body: (compound_statement) @syntax.function.body) @syntax.function.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c",
                confidence=0.95,
                metadata={
                    "relationships": C_PATTERN_RELATIONSHIPS["function_definition"],
                    "metrics": C_PATTERN_METRICS["function_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "struct_definition": TreeSitterResilientPattern(
                name="struct_definition",
                pattern="""
                [
                    (struct_specifier
                        name: (type_identifier) @syntax.struct.name
                        body: (field_declaration_list) @syntax.struct.fields) @syntax.struct.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c",
                confidence=0.95,
                metadata={
                    "relationships": C_PATTERN_RELATIONSHIPS["struct_definition"],
                    "metrics": C_PATTERN_METRICS["struct_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            ),
            
            "enum_definition": TreeSitterResilientPattern(
                name="enum_definition",
                pattern="""
                [
                    (enum_specifier
                        name: (type_identifier) @syntax.enum.name
                        body: (enumerator_list) @syntax.enum.values) @syntax.enum.def
                ]
                """,
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c",
                confidence=0.95,
                metadata={
                    "relationships": C_PATTERN_RELATIONSHIPS["enum_definition"],
                    "metrics": C_PATTERN_METRICS["enum_definition"],
                    "validation": PatternValidationResult(
                        is_valid=True,
                        validation_time=0.0
                    )
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "variable_declaration": TreeSitterAdaptivePattern(
                name="variable_declaration",
                pattern="""
                [
                    (declaration
                        type: (_) @semantics.var.type
                        declarator: (init_declarator
                            declarator: (identifier) @semantics.var.name
                            value: (_)? @semantics.var.value)) @semantics.var.def
                ]
                """,
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c",
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
            "comments": TreeSitterAdaptivePattern(
                name="comments",
                pattern="""
                [
                    (comment) @documentation.comment
                ]
                """,
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="c",
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

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        # The following patterns were using regexes, which is not allowed for C (tree-sitter only). Commented out for correctness.
        # "buffer_overflow": QueryPattern(
        #     name="buffer_overflow",
        #     pattern=r'(?:strcpy|strcat|sprintf|gets)\s*\([^)]+\)',
        #     extract=lambda m: {
        #         "type": "buffer_overflow",
        #         "content": m.group(0),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "confidence": 0.9
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id="c",
        #     metadata={"description": "Detects potential buffer overflows", "examples": ["strcpy(dest, src);"]}
        # ),
        # "memory_leak": QueryPattern(
        #     name="memory_leak",
        #     pattern=r'malloc\s*\([^)]+\)(?![^;]*free)',
        #     extract=lambda m: {
        #         "type": "memory_leak",
        #         "content": m.group(0),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "confidence": 0.85
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id="c",
        #     metadata={"description": "Detects potential memory leaks", "examples": ["ptr = malloc(size);"]}
        # ),
        # "null_pointer_deref": QueryPattern(
        #     name="null_pointer_deref",
        #     pattern=r'([a-zA-Z_][a-zA-Z0-9_]*)\s*->\s*[a-zA-Z_][a-zA-Z0-9_]*',
        #     extract=lambda m: {
        #         "type": "null_pointer_deref",
        #         "pointer": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "needs_verification": True
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id="c",
        #     metadata={"description": "Detects potential null pointer dereferences", "examples": ["ptr->field;"]}
        # ),
        # "uninitialized_variable": QueryPattern(
        #     name="uninitialized_variable",
        #     pattern=r'(?:int|char|float|double|long)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;',
        #     extract=lambda m: {
        #         "type": "uninitialized_variable",
        #         "variable": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "confidence": 0.8
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id="c",
        #     metadata={"description": "Detects potentially uninitialized variables", "examples": ["int x;"]}
        # ),
        # "format_string_vulnerability": QueryPattern(
        #     name="format_string_vulnerability",
        #     pattern=r'printf\s*\(\s*([^,)]+)\s*\)',
        #     extract=lambda m: {
        #         "type": "format_string_vulnerability",
        #         "format_string": m.group(1),
        #         "line_number": m.string.count('\n', 0, m.start()) + 1,
        #         "confidence": 0.9
        #     },
        #     category=PatternCategory.COMMON_ISSUES,
        #     purpose=PatternPurpose.UNDERSTANDING,
        #     language_id="c",
        #     metadata={"description": "Detects format string vulnerabilities", "examples": ["printf(user_input);"]}
        # ),
    }
}

def create_pattern_context(file_path: str, code_structure: Dict[str, Any]) -> PatternContext:
    """Create pattern context for C files."""
    return PatternContext(
        code_structure=code_structure,
        language_stats={"language": "c", "version": "c11"},
        project_patterns=[],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(C_PATTERNS.keys())
    )

def get_c_pattern_relationships(pattern_name: str) -> List[PatternRelationship]:
    """Get relationships for a specific pattern."""
    return C_PATTERN_RELATIONSHIPS.get(pattern_name, [])

def update_c_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in C_PATTERN_METRICS:
        pattern_metrics = C_PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_c_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=get_c_pattern_relationships(pattern_name),
        performance=C_PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "c"}
    )

class CPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced C pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = None
        self._ai_processor = None
        self._block_extractor = None
        self._unified_parser = None
        self._metrics = {
            "total_patterns": 0,
            "learned_patterns": 0,
            "failed_patterns": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "learning_times": []
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self):
        """Initialize with C-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await get_feature_extractor("c")
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register C patterns
        from parsers.pattern_processor import pattern_processor
        await self._pattern_processor.register_language_patterns(
            "c", 
            C_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "c_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(C_PATTERNS),
                "capabilities": list(C_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="c",
                file_type=FileType.CODE,
                interaction_type=InteractionType.LEARNING,
                repository_id=None,
                file_path=project_path
            )
            
            ai_result = await self._ai_processor.process_with_ai(
                source_code="",  # Will be filled by processor
                context=ai_context
            )
            
            learned_patterns = []
            if ai_result.success:
                learned_patterns.extend(ai_result.learned_patterns)
                self._metrics["learned_patterns"] += len(ai_result.learned_patterns)
            
            # Then do cross-project learning through base class
            project_patterns = await self._extract_project_patterns(project_path)
            await self._integrate_patterns(project_patterns, project_path)
            learned_patterns.extend(project_patterns)
            
            # Finally add C-specific patterns
            async with AsyncErrorBoundary("c_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "c",
                    "",  # Will be filled from files
                    None
                )
                
                # Extract features with metrics
                features = []
                for block in blocks:
                    block_features = await self._feature_extractor.extract_features(
                        block.content,
                        block.metadata
                    )
                    features.append(block_features)
                
                # Learn patterns from features
                c_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(c_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "c_pattern_learner",
                ComponentStatus.HEALTHY,
                details={
                    "learned_patterns": len(learned_patterns),
                    "learning_time": learning_time
                }
            )
            
            return learned_patterns
            
        except Exception as e:
            self._metrics["failed_patterns"] += 1
            await log(f"Error learning patterns: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                "c_pattern_learner",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            return []

    async def cleanup(self):
        """Clean up pattern learner resources."""
        try:
            # Clean up base class resources
            await super().cleanup()
            
            # Clean up specific components
            if self._feature_extractor:
                await self._feature_extractor.cleanup()
            if self._block_extractor:
                await self._block_extractor.cleanup()
            if self._unified_parser:
                await self._unified_parser.cleanup()
            if self._ai_processor:
                await self._ai_processor.cleanup()
            
            # Update final status
            await global_health_monitor.update_component_status(
                "c_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "c_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_c_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a C pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to C-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await get_feature_extractor("c")
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "c", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks
        blocks = await block_extractor.get_child_blocks(
            "c",
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
        await update_c_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        return matches

# Initialize pattern learner
c_pattern_learner = CPatternLearner()

async def initialize_c_patterns():
    """Initialize C patterns during app startup."""
    global c_pattern_learner
    
    # Initialize pattern processor first
    from parsers.pattern_processor import pattern_processor
    await pattern_processor.initialize()
    
    # Register C patterns
    await pattern_processor.register_language_patterns(
        "c",
        C_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": C_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    c_pattern_learner = await CPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "c",
        c_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "c_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(C_PATTERNS),
            "capabilities": list(C_CAPABILITIES)
        }
    )

async def extract_c_features(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> ExtractedFeatures:
    """Extract features from pattern matches."""
    from parsers.pattern_processor import pattern_processor
    feature_extractor = await get_feature_extractor("c")
    
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

async def validate_c_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    context: Optional[PatternContext] = None
) -> PatternValidationResult:
    """Validate a C pattern with system integration."""
    # First try common pattern validation
    common_result = await validate_tree_sitter_pattern(pattern, context)
    if common_result.is_valid:
        return common_result
    
    # Fall back to C-specific validation
    async with AsyncErrorBoundary("c_pattern_validation"):
        # Get pattern processor
        from parsers.pattern_processor import pattern_processor
        validation_result = await pattern_processor.validate_pattern(
            pattern,
            language_id="c",
            context=context
        )
        
        # Update pattern metrics
        if not validation_result.is_valid:
            pattern_metrics = C_PATTERN_METRICS.get(pattern.name)
            if pattern_metrics:
                pattern_metrics.error_count += 1
        
        return validation_result

# Export public interfaces
__all__ = [
    'C_PATTERNS',
    'C_PATTERN_RELATIONSHIPS',
    'C_PATTERN_METRICS',
    'create_pattern_context',
    'get_c_pattern_relationships',
    'update_c_pattern_metrics',
    'get_c_pattern_match_result'
]

# Module identification - using the consistent language ID
LANGUAGE_ID = "c" 