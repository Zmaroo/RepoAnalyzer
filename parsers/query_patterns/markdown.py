"""Query patterns for Markdown files.

This module provides Markdown-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from .common import COMMON_PATTERNS, COMMON_CAPABILITIES, process_common_pattern
from .enhanced_patterns import AdaptivePattern, ResilientPattern, CrossProjectPatternLearner
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
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

# Markdown capabilities (extends common capabilities)
MARKDOWN_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.DOCUMENTATION,
    AICapability.FORMATTING,
    AICapability.DIAGRAMS
}

# Language identifier
LANGUAGE = "markdown"

@dataclass
class MarkdownPatternContext(PatternContext):
    """Markdown-specific pattern context."""
    heading_levels: Set[int] = field(default_factory=set)
    link_refs: Set[str] = field(default_factory=set)
    code_langs: Set[str] = field(default_factory=set)
    has_frontmatter: bool = False
    has_math: bool = False
    has_mermaid: bool = False
    nesting_level: int = 0
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.heading_levels)}:{self.nesting_level}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "heading": PatternPerformanceMetrics(),
    "list": PatternPerformanceMetrics(),
    "code": PatternPerformanceMetrics(),
    "link": PatternPerformanceMetrics(),
    "emphasis": PatternPerformanceMetrics()
}

MARKDOWN_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "heading": ResilientPattern(
                pattern=r'^(#{1,6})\s+(.+)$',
                extract=lambda m: {
                    "type": "heading",
                    "level": len(m.group(1)),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINS: ["emphasis", "link"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="heading",
                description="Matches Markdown headers",
                examples=["# Title", "## Section"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["heading"],
                    "validation": {
                        "required_fields": ["level", "content"],
                        "level_range": [1, 6]
                    }
                }
            ),
            "list": ResilientPattern(
                pattern=r'^(\s*)[*+-]\s+(.+)$',
                extract=lambda m: {
                    "type": "list",
                    "indent": len(m.group(1)),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINS: ["list", "emphasis", "link"],
                        PatternRelationType.DEPENDS_ON: []
                    }
                },
                name="list",
                description="Matches unordered list items",
                examples=["* Item", "- Point"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["list"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "emphasis": AdaptivePattern(
                pattern=r'(\*\*|__)(.*?)\1|(\*|_)(.*?)\3',
                extract=lambda m: {
                    "type": "emphasis",
                    "style": "strong" if m.group(1) else "emphasis",
                    "content": m.group(2) or m.group(4),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="emphasis",
                description="Matches text emphasis",
                examples=["**bold**", "_italic_"],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["emphasis"],
                    "validation": {
                        "required_fields": ["content", "style"]
                    }
                }
            ),
            "link": AdaptivePattern(
                pattern=r'\[([^\]]+)\]\(([^)]+)\)',
                extract=lambda m: {
                    "type": "link",
                    "text": m.group(1),
                    "url": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
                        PatternRelationType.REFERENCES: ["link_ref"]
                    }
                },
                name="link",
                description="Matches links",
                examples=["[text](url)"],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["link"],
                    "validation": {
                        "required_fields": ["text", "url"]
                    }
                }
            )
        }
    },
    
    PatternCategory.LEARNING: {
        PatternPurpose.CODE_BLOCKS: {
            "code_block": AdaptivePattern(
                pattern=r'```(\w*)\n(.*?)```',
                extract=lambda m: {
                    "type": "code_block",
                    "language": m.group(1),
                    "content": m.group(2),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["document"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="code_block",
                description="Matches code blocks",
                examples=["```python\nprint('hello')\n```"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.CODE_BLOCKS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["code"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        },
        PatternPurpose.DIAGRAMS: {
            "mermaid": AdaptivePattern(
                pattern=r'```mermaid\n(.*?)```',
                extract=lambda m: {
                    "type": "mermaid",
                    "content": m.group(1),
                    "line_number": m.string.count('\n', 0, m.start()) + 1,
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["document"],
                        PatternRelationType.REFERENCES: []
                    }
                },
                name="mermaid",
                description="Matches Mermaid diagrams",
                examples=["```mermaid\ngraph TD;\nA-->B;\n```"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DIAGRAMS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["diagram"],
                    "validation": {
                        "required_fields": ["content"]
                    }
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "broken_link": QueryPattern(
            name="broken_link",
            pattern=r'\[([^\]]+)\]\(([^)]+)\)',
            extract=lambda m: {
                "type": "broken_link",
                "text": m.group(1),
                "url": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially broken links", "examples": ["[text](broken-url)"]}
        ),
        "invalid_header": QueryPattern(
            name="invalid_header",
            pattern=r'^#{7,}|^#+[^# \t]',
            extract=lambda m: {
                "type": "invalid_header",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects invalid headers", "examples": ["####### Too many", "#Invalid"]}
        ),
        "broken_reference": QueryPattern(
            name="broken_reference",
            pattern=r'\[([^\]]+)\]\[([^\]]*)\](?!\s*\[)',
            extract=lambda m: {
                "type": "broken_reference",
                "text": m.group(1),
                "ref": m.group(2) or m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects broken reference-style links", "examples": ["[text][missing-ref]"]}
        ),
        "malformed_table": QueryPattern(
            name="malformed_table",
            pattern=r'\|[^|\n]*\|[^|\n]*\n(?!\s*\|[-:]+\|)',
            extract=lambda m: {
                "type": "malformed_table",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects malformed tables", "examples": ["|Header|\n|Content|"]}
        ),
        "unclosed_code_block": QueryPattern(
            name="unclosed_code_block",
            pattern=r'```[^\n]*\n(?:(?!```).)*$',
            extract=lambda m: {
                "type": "unclosed_code_block",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects unclosed code blocks", "examples": ["```python\nprint('hello')"]}
        )
    }
}

class MarkdownPatternLearner(CrossProjectPatternLearner):
    """Enhanced Markdown pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        super().__init__()
        self._feature_extractor = None
        self._pattern_processor = pattern_processor
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
        """Initialize with Markdown-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("markdown", FileType.DOCUMENTATION)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Markdown patterns
        await self._pattern_processor.register_language_patterns(
            "markdown", 
            MARKDOWN_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "markdown_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(MARKDOWN_PATTERNS),
                "capabilities": list(MARKDOWN_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="markdown",
                file_type=FileType.DOCUMENTATION,
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
            
            # Finally add Markdown-specific patterns
            async with AsyncErrorBoundary("markdown_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "markdown",
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
                markdown_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(markdown_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "markdown_pattern_learner",
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
                "markdown_pattern_learner",
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
                "markdown_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "markdown_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_markdown_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Markdown pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Markdown-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("markdown", FileType.DOCUMENTATION)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "markdown", FileType.DOCUMENTATION)
            if parse_result and parse_result.ast:
                context = await create_markdown_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"markdown_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "markdown",
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
        
        # Cache the result
        await get_current_request_cache().set(cache_key, matches)
        
        # Update pattern metrics
        await update_markdown_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "markdown_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_markdown_pattern_context(
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
            language_id="markdown",
            file_type=FileType.DOCUMENTATION
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "markdown"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(MARKDOWN_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_markdown_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
    """Update performance metrics for a pattern."""
    if pattern_name in PATTERN_METRICS:
        pattern_metrics = PATTERN_METRICS[pattern_name]
        pattern_metrics.execution_time = metrics.get("execution_time", 0.0)
        pattern_metrics.memory_usage = metrics.get("memory_usage", 0)
        pattern_metrics.cache_hits = metrics.get("cache_hits", 0)
        pattern_metrics.cache_misses = metrics.get("cache_misses", 0)
        pattern_metrics.error_count = metrics.get("error_count", 0)
        
        total = pattern_metrics.cache_hits + pattern_metrics.cache_misses
        if total > 0:
            pattern_metrics.success_rate = pattern_metrics.cache_hits / total

def get_markdown_pattern_match_result(
    pattern_name: str,
    matches: List[Dict[str, Any]],
    context: PatternContext
) -> PatternMatchResult:
    """Create a pattern match result with relationships and metrics."""
    return PatternMatchResult(
        pattern_name=pattern_name,
        matches=matches,
        context=context,
        relationships=PATTERN_RELATIONSHIPS.get(pattern_name, []),
        performance=PATTERN_METRICS.get(pattern_name, PatternPerformanceMetrics()),
        validation=PatternValidationResult(is_valid=True),
        metadata={"language": "markdown"}
    )

# Initialize pattern learner
pattern_learner = MarkdownPatternLearner()

async def initialize_markdown_patterns():
    """Initialize Markdown patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Markdown patterns
    await pattern_processor.register_language_patterns(
        "markdown",
        MARKDOWN_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": MARKDOWN_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await MarkdownPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "markdown",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "markdown_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(MARKDOWN_PATTERNS),
            "capabilities": list(MARKDOWN_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "heading": {
        PatternRelationType.CONTAINS: ["emphasis", "link"],
        PatternRelationType.DEPENDS_ON: []
    },
    "list": {
        PatternRelationType.CONTAINS: ["list", "emphasis", "link"],
        PatternRelationType.DEPENDS_ON: []
    },
    "emphasis": {
        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
        PatternRelationType.REFERENCES: []
    },
    "link": {
        PatternRelationType.CONTAINED_BY: ["heading", "list", "paragraph"],
        PatternRelationType.REFERENCES: ["link_ref"]
    },
    "code_block": {
        PatternRelationType.CONTAINED_BY: ["document"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'MARKDOWN_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_markdown_pattern_match_result',
    'update_markdown_pattern_metrics',
    'MarkdownPatternContext',
    'pattern_learner'
]
