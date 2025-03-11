"""Query patterns for HTML files with enhanced pattern support.

This module provides HTML-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Match, Optional, Set, Union
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ErrorSeverity
from utils.health_monitor import monitor_operation, global_health_monitor, ComponentStatus
from utils.request_cache import cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.logger import log
from utils.shutdown import register_shutdown_handler
from parsers.pattern_processor import pattern_processor
from parsers.block_extractor import get_block_extractor
from parsers.feature_extractor import BaseFeatureExtractor
from parsers.unified_parser import get_unified_parser
from parsers.base_parser import BaseParser
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.ai_pattern_processor import get_ai_pattern_processor
import time

# Language identifier
LANGUAGE = "html"

@dataclass
class HTMLPatternContext(PatternContext):
    """HTML-specific pattern context."""
    tag_names: Set[str] = field(default_factory=set)
    attribute_names: Set[str] = field(default_factory=set)
    script_types: Set[str] = field(default_factory=set)
    style_types: Set[str] = field(default_factory=set)
    has_head: bool = False
    has_body: bool = False
    has_scripts: bool = False
    has_styles: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.tag_names)}:{len(self.script_types)}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "element": PatternPerformanceMetrics(),
    "attribute": PatternPerformanceMetrics(),
    "script": PatternPerformanceMetrics(),
    "style": PatternPerformanceMetrics(),
    "comment": PatternPerformanceMetrics(),
    "doctype": PatternPerformanceMetrics()
}

def extract_element(match: Match) -> Dict[str, Any]:
    """Extract element information."""
    return {
        "type": "element",
        "tag": match.group(1),
        "attributes": match.group(2) if match.group(2) else "",
        "content": match.group(3) if match.group(3) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINS: ["element", "text", "comment"],
            PatternRelationType.DEPENDS_ON: []
        }
    }

def extract_attribute(match: Match) -> Dict[str, Any]:
    """Extract attribute information."""
    return {
        "type": "attribute",
        "name": match.group(1),
        "value": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINED_BY: ["element"],
            PatternRelationType.REFERENCES: []
        }
    }

def extract_script(match: Match) -> Dict[str, Any]:
    """Extract script information."""
    return {
        "type": "script",
        "attributes": match.group(1) if match.group(1) else "",
        "content": match.group(2) if match.group(2) else "",
        "line_number": match.string.count('\n', 0, match.start()) + 1,
        "relationships": {
            PatternRelationType.CONTAINED_BY: ["head", "body"],
            PatternRelationType.DEPENDS_ON: ["script"]
        }
    }

HTML_PATTERNS = {
    PatternCategory.SYNTAX: {
        "element": ResilientPattern(
            pattern=r'<(\w+)([^>]*)(?:>(.*?)</\1>|/>)',
            extract=extract_element,
            description="Matches HTML elements",
            examples=["<div class=\"container\">content</div>", "<img src=\"image.jpg\" />"],
            name="element",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["element"],
                "validation": {
                    "required_fields": ["tag"],
                    "tag_format": r'^[a-zA-Z][a-zA-Z0-9]*$'
                }
            }
        ),
        "attribute": ResilientPattern(
            pattern=r'\s(\w+)(?:=(["\'][^"\']*["\']))?',
            extract=extract_attribute,
            description="Matches HTML attributes",
            examples=["class=\"container\"", "disabled"],
            name="attribute",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["attribute"],
                "validation": {
                    "required_fields": ["name"],
                    "name_format": r'^[a-zA-Z][a-zA-Z0-9-]*$'
                }
            }
        ),
        "doctype": ResilientPattern(
            pattern=r'<!DOCTYPE[^>]*>',
            extract=lambda m: {
                "type": "doctype",
                "declaration": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.DEPENDS_ON: [],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches DOCTYPE declarations",
            examples=["<!DOCTYPE html>"],
            name="doctype",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["doctype"],
                "validation": {
                    "required_fields": ["declaration"]
                }
            }
        ),
        "text_content": ResilientPattern(
            pattern=r'>([^<]+)<',
            extract=lambda m: {
                "type": "text",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches text content",
            examples=[">Some text<"],
            name="text_content",
            category=PatternCategory.SYNTAX,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["text"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        )
    },
    
    PatternCategory.STRUCTURE: {
        "head": AdaptivePattern(
            pattern=r'<head[^>]*>(.*?)</head>',
            extract=lambda m: {
                "type": "head",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["meta", "title", "link", "script", "style"],
                    PatternRelationType.CONTAINED_BY: ["html"]
                }
            },
            description="Matches head section",
            examples=["<head><title>Page Title</title></head>"],
            name="head",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["head"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "body": AdaptivePattern(
            pattern=r'<body[^>]*>(.*?)</body>',
            extract=lambda m: {
                "type": "body",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["element", "script", "style"],
                    PatternRelationType.CONTAINED_BY: ["html"]
                }
            },
            description="Matches body section",
            examples=["<body><div>content</div></body>"],
            name="body",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["body"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "container": AdaptivePattern(
            pattern=r'<(div|section|article|main|aside|nav|header|footer)[^>]*>(.*?)</\1>',
            extract=lambda m: {
                "type": "container",
                "tag": m.group(1),
                "content": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINS: ["element", "text", "comment"],
                    PatternRelationType.CONTAINED_BY: ["body", "container"]
                }
            },
            description="Matches structural containers",
            examples=["<div class=\"container\">content</div>"],
            name="container",
            category=PatternCategory.STRUCTURE,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.9,
            metadata={
                "metrics": PATTERN_METRICS["container"],
                "validation": {
                    "required_fields": ["tag", "content"],
                    "tag_format": r'^[a-z]+$'
                }
            }
        )
    },
    
    PatternCategory.DOCUMENTATION: {
        "comment": ResilientPattern(
            pattern=r'<!--(.*?)-->',
            extract=lambda m: {
                "type": "comment",
                "content": m.group(1).strip(),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element", "head", "body"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches HTML comments",
            examples=["<!-- Navigation menu -->"],
            name="comment",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["comment"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "meta": ResilientPattern(
            pattern=r'<meta\s+([^>]*)>',
            extract=lambda m: {
                "type": "meta",
                "attributes": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["head"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches meta tags",
            examples=["<meta name=\"description\" content=\"Page description\">"],
            name="meta",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["meta"],
                "validation": {
                    "required_fields": ["attributes"]
                }
            }
        ),
        "aria_label": ResilientPattern(
            pattern=r'aria-label=(["\'][^"\']*["\'])',
            extract=lambda m: {
                "type": "aria_label",
                "label": m.group(1).strip('\'"'),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["element"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches ARIA labels",
            examples=["aria-label=\"Close button\""],
            name="aria_label",
            category=PatternCategory.DOCUMENTATION,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["aria_label"],
                "validation": {
                    "required_fields": ["label"]
                }
            }
        )
    },
    
    PatternCategory.CODE_PATTERNS: {
        "script": ResilientPattern(
            pattern=r'<script([^>]*)>(.*?)</script>',
            extract=extract_script,
            description="Matches script elements",
            examples=["<script>console.log('Hello');</script>"],
            name="script",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["script"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "style": ResilientPattern(
            pattern=r'<style[^>]*>(.*?)</style>',
            extract=lambda m: {
                "type": "style",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["head"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches style elements",
            examples=["<style>.class { color: red; }</style>"],
            name="style",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["style"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        ),
        "template": ResilientPattern(
            pattern=r'<template[^>]*>(.*?)</template>',
            extract=lambda m: {
                "type": "template",
                "content": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "relationships": {
                    PatternRelationType.CONTAINED_BY: ["body"],
                    PatternRelationType.REFERENCES: []
                }
            },
            description="Matches template elements",
            examples=["<template><div>template content</div></template>"],
            name="template",
            category=PatternCategory.CODE_PATTERNS,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            confidence=0.95,
            metadata={
                "metrics": PATTERN_METRICS["template"],
                "validation": {
                    "required_fields": ["content"]
                }
            }
        )
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "unclosed_tag": QueryPattern(
            name="unclosed_tag",
            pattern=r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>(?:(?!</\1>).)*$',
            extract=lambda m: {
                "type": "unclosed_tag",
                "tag": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects unclosed HTML tags", "examples": ["<div>content"]}
        ),
        "invalid_nesting": QueryPattern(
            name="invalid_nesting",
            pattern=r'<([a-zA-Z][a-zA-Z0-9]*)>[^<]*<([a-zA-Z][a-zA-Z0-9]*)>[^<]*</\1>',
            extract=lambda m: {
                "type": "invalid_nesting",
                "outer_tag": m.group(1),
                "inner_tag": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects invalid tag nesting", "examples": ["<div><p>text</div>"]}
        ),
        "duplicate_id": QueryPattern(
            name="duplicate_id",
            pattern=r'id=["\']([^"\']+)["\'][^>]*>.*?id=["\']\\1["\']',
            extract=lambda m: {
                "type": "duplicate_id",
                "id": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects duplicate IDs", "examples": ["<div id=\"dup\"></div><span id=\"dup\"></span>"]}
        ),
        "invalid_attribute": QueryPattern(
            name="invalid_attribute",
            pattern=r'<[^>]+\s([a-zA-Z]+)(?!=)[^>]*>',
            extract=lambda m: {
                "type": "invalid_attribute",
                "attribute": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects invalid attribute syntax", "examples": ["<div class></div>"]}
        ),
        "broken_reference": QueryPattern(
            name="broken_reference",
            pattern=r'href=["\']#([^"\']+)["\']',
            extract=lambda m: {
                "type": "broken_reference",
                "reference": m.group(1),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE,
            metadata={"description": "Detects potentially broken internal references", "examples": ["<a href=\"#missing\">link</a>"]}
        )
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_html_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from HTML content for repository learning."""
    patterns = []
    context = HTMLPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in HTML_PATTERNS:
                category_patterns = HTML_PATTERNS[category]
                for pattern_name, pattern in category_patterns.items():
                    if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                        try:
                            matches = await pattern.matches(content, context)
                            for match in matches:
                                patterns.append({
                                    "name": pattern_name,
                                    "category": category.value,
                                    "content": match.get("text", ""),
                                    "metadata": match,
                                    "confidence": pattern.confidence,
                                    "relationships": match.get("relationships", {})
                                })
                                
                                # Update context
                                if match["type"] == "element":
                                    context.tag_names.add(match["tag"])
                                elif match["type"] == "script":
                                    context.has_scripts = True
                                    if "type" in match["attributes"]:
                                        context.script_types.add(match["attributes"]["type"])
                                elif match["type"] == "style":
                                    context.has_styles = True
                                    if "type" in match["attributes"]:
                                        context.style_types.add(match["attributes"]["type"])
                                elif match["type"] == "head":
                                    context.has_head = True
                                elif match["type"] == "body":
                                    context.has_body = True
                                
                        except Exception as e:
                            await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                            continue
    
    except Exception as e:
        await log(f"Error extracting HTML patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "element": {
        PatternRelationType.CONTAINS: ["element", "text", "comment"],
        PatternRelationType.CONTAINED_BY: ["element", "body"]
    },
    "head": {
        PatternRelationType.CONTAINS: ["meta", "title", "link", "script", "style"],
        PatternRelationType.CONTAINED_BY: ["html"]
    },
    "body": {
        PatternRelationType.CONTAINS: ["element", "script", "style"],
        PatternRelationType.CONTAINED_BY: ["html"]
    },
    "script": {
        PatternRelationType.CONTAINED_BY: ["head", "body"],
        PatternRelationType.DEPENDS_ON: ["script"]
    },
    "style": {
        PatternRelationType.CONTAINED_BY: ["head"],
        PatternRelationType.REFERENCES: []
    }
}

# Export public interfaces
__all__ = [
    'HTML_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_html_patterns_for_learning',
    'HTMLPatternContext',
    'pattern_learner'
]

class HTMLPatternLearner(CrossProjectPatternLearner):
    """Enhanced HTML pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with HTML-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("html", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register HTML patterns
        await self._pattern_processor.register_language_patterns(
            "html", 
            HTML_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "html_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(HTML_PATTERNS),
                "capabilities": list(HTML_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="html",
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
            
            # Finally add HTML-specific patterns
            async with AsyncErrorBoundary("html_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "html",
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
                html_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(html_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "html_pattern_learner",
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
                "html_pattern_learner",
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
                "html_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "html_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_html_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process an HTML pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to HTML-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("html", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "html", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_html_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"html_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "html",
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
        await update_html_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "html_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_html_pattern_context(
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
            language_id="html",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "html"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(HTML_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

# Initialize pattern learner
html_pattern_learner = HTMLPatternLearner()

async def initialize_html_patterns():
    """Initialize HTML patterns during app startup."""
    global html_pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register HTML patterns
    await pattern_processor.register_language_patterns(
        "html",
        HTML_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": HTML_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    html_pattern_learner = await HTMLPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "html",
        html_pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "html_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(HTML_PATTERNS),
            "capabilities": list(HTML_CAPABILITIES)
        }
    )