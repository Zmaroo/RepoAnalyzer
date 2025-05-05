"""Query patterns for Python files.

This module provides Python-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, ParserType
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

# Language identifier
LANGUAGE_ID = "python"

# Python capabilities (extends common capabilities)
PYTHON_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.OBJECT_ORIENTED,
    AICapability.FUNCTIONAL_PROGRAMMING,
    AICapability.TYPE_HINTS
}

# Tree-sitter specific queries for Python
TS_QUERIES = {
    "functions": """
    (function_definition
      name: (identifier) @function.name
      parameters: (parameters) @function.params
      body: (block) @function.body)
    """,
    
    "classes": """
    (class_definition
      name: (identifier) @class.name
      body: (block) @class.body)
      
    (class_definition
      name: (identifier) @class.name
      superclasses: (argument_list) @class.superclasses
      body: (block) @class.body)
    """,
    
    "imports": """
    (import_statement
      name: (dotted_name) @import.module)
      
    (import_from_statement
      module_name: (dotted_name) @import.from_module
      name: (dotted_name) @import.name)
    """,
    
    "docstrings": """
    (module 
      (expression_statement
        (string) @docstring.module))
        
    (function_definition
      body: (block
        (expression_statement
          (string) @docstring.function) . _))
          
    (class_definition
      body: (block
        (expression_statement
          (string) @docstring.class) . _))
    """,
    
    "decorators": """
    (decorator
      name: (identifier) @decorator.name
      arguments: (argument_list)? @decorator.arguments)
      
    (decorated_definition
      (decorator) @decorator.decorator
      definition: (function_definition) @decorator.function)
      
    (decorated_definition
      (decorator) @decorator.decorator
      definition: (class_definition) @decorator.class)
    """,
    
    "async_functions": """
    (function_definition
      "async" @async.keyword
      name: (identifier) @async.function)
    """,
    
    "type_hints": """
    (function_definition
      parameters: (parameters
        (typed_parameter
          type: (_) @type_hint.parameter_type)))
          
    (function_definition
      return_type: (_) @type_hint.return_type)
      
    (variable_declaration
      (typed_variable
        type: (_) @type_hint.variable_type))
    """,
    
    "error_handling": """
    (try_statement
      body: (block) @error.try_body
      (except_clause
        type: (_)? @error.except_type
        body: (block) @error.except_body)* 
      (finally_clause
        body: (block) @error.finally_body)?)
    """,
    
    "comprehensions": """
    (list_comprehension) @comprehension.list
    (dictionary_comprehension) @comprehension.dict
    (set_comprehension) @comprehension.set
    (generator_expression) @comprehension.generator
    """
}

@dataclass
class PythonPatternContext(PatternContext):
    """Python-specific pattern context."""
    class_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    decorator_names: Set[str] = field(default_factory=set)
    has_type_hints: bool = False
    has_async: bool = False
    has_decorators: bool = False
    has_dataclasses: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.class_names)}:{self.has_type_hints}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "decorator": PatternPerformanceMetrics(),
    "import": PatternPerformanceMetrics()
}

PYTHON_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "class": TreeSitterResilientPattern(
                pattern="""
                [
                    (class_definition
                        name: (identifier) @syntax.class.name
                        superclasses: (argument_list)? @syntax.class.bases
                        body: (block) @syntax.class.body) @syntax.class.def,
                    (decorated_definition
                        decorators: (decorator)+ @syntax.class.decorator
                        definition: (class_definition
                            name: (identifier) @syntax.class.decorated.name
                            superclasses: (argument_list)? @syntax.class.decorated.bases
                            body: (block) @syntax.class.decorated.body)) @syntax.class.decorated.def
                ]
                """,
                extract=lambda node: {
                    "type": "class",
                    "name": (
                        node["captures"].get("syntax.class.name", {}).get("text", "") or
                        node["captures"].get("syntax.class.decorated.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "is_decorated": "syntax.class.decorated.def" in node["captures"],
                    "has_bases": (
                        "syntax.class.bases" in node["captures"] or
                        "syntax.class.decorated.bases" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["method", "property", "decorator"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="class",
                description="Matches Python class declarations",
                examples=["class MyClass(BaseClass):", "@dataclass\nclass Config:"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": TreeSitterResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.func.name
                        parameters: (parameters) @syntax.func.params
                        return_type: (type)? @syntax.func.return
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (decorated_definition
                        decorators: (decorator)+ @syntax.func.decorator
                        definition: (function_definition
                            name: (identifier) @syntax.func.decorated.name
                            parameters: (parameters) @syntax.func.decorated.params
                            return_type: (type)? @syntax.func.decorated.return
                            body: (block) @syntax.func.decorated.body)) @syntax.func.decorated.def,
                    (async_function_definition
                        name: (identifier) @syntax.async.name
                        parameters: (parameters) @syntax.async.params
                        return_type: (type)? @syntax.async.return
                        body: (block) @syntax.async.body) @syntax.async.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.func.decorated.name", {}).get("text", "") or
                        node["captures"].get("syntax.async.name", {}).get("text", "")
                    ),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_decorated": "syntax.func.decorated.def" in node["captures"],
                    "is_async": "syntax.async.def" in node["captures"],
                    "has_return_type": (
                        "syntax.func.return" in node["captures"] or
                        "syntax.func.decorated.return" in node["captures"] or
                        "syntax.async.return" in node["captures"]
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "block", "decorator"],
                        PatternRelationType.DEPENDS_ON: ["class", "module"]
                    }
                },
                name="function",
                description="Matches Python function declarations",
                examples=["def process(data: str) -> None:", "@property\ndef name(self):"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE_ID,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DECORATORS: {
            "decorator": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (decorator
                        name: (identifier) @dec.name
                        arguments: (argument_list)? @dec.args) @dec.def,
                    (decorator
                        name: (attribute) @dec.attr.name
                        arguments: (argument_list)? @dec.attr.args) @dec.attr.def
                ]
                """,
                extract=lambda node: {
                    "type": "decorator",
                    "line_number": node["captures"].get("dec.def", {}).get("start_point", [0])[0],
                    "name": (
                        node["captures"].get("dec.name", {}).get("text", "") or
                        node["captures"].get("dec.attr.name", {}).get("text", "")
                    ),
                    "has_arguments": (
                        "dec.args" in node["captures"] or
                        "dec.attr.args" in node["captures"]
                    ),
                    "is_attribute": "dec.attr.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["class", "function", "method"],
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="decorator",
                description="Matches Python decorators",
                examples=["@property", "@dataclass(frozen=True)"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.DECORATORS,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["decorator"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        },
        PatternPurpose.IMPORTS: {
            "import": TreeSitterAdaptivePattern(
                pattern="""
                [
                    (import_statement
                        name: (dotted_name) @import.name) @import.def,
                    (import_from_statement
                        module_name: (dotted_name) @import.from.module
                        name: (dotted_name) @import.from.name) @import.from.def,
                    (aliased_import
                        name: (dotted_name) @import.alias.name
                        alias: (identifier) @import.alias.as) @import.alias.def
                ]
                """,
                extract=lambda node: {
                    "type": "import",
                    "line_number": node["captures"].get("import.def", {}).get("start_point", [0])[0],
                    "name": (
                        node["captures"].get("import.name", {}).get("text", "") or
                        node["captures"].get("import.from.name", {}).get("text", "")
                    ),
                    "module": node["captures"].get("import.from.module", {}).get("text", ""),
                    "alias": node["captures"].get("import.alias.as", {}).get("text", ""),
                    "is_from": "import.from.def" in node["captures"],
                    "is_aliased": "import.alias.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.DEPENDS_ON: ["module"]
                    }
                },
                name="import",
                description="Matches Python import statements",
                examples=["import os", "from typing import List", "import numpy as np"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.IMPORTS,
                language_id=LANGUAGE_ID,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["import"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_.]*$'
                    }
                }
            )
        }
    },

    PatternCategory.BEST_PRACTICES: {
        # ... existing patterns ...
    },

    PatternCategory.COMMON_ISSUES: {
        "indentation_error": QueryPattern(
            name="indentation_error",
            pattern=r'^\s+[^\s#].*\n^(?!\s)',
            extract=lambda m: {
                "type": "indentation_error",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.9
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potential indentation errors", "examples": ["    def func():\nprint('bad')"]}
        ),
        "undefined_variable": QueryPattern(
            name="undefined_variable",
            pattern=r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|\+=|-=|\*=|/=|%=)\s*([^=\n]+)$',
            extract=lambda m: {
                "type": "undefined_variable",
                "variable": m.group(1),
                "value": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potential undefined variable usage", "examples": ["x = y + 1  # y might be undefined"]}
        ),
        "circular_import": QueryPattern(
            name="circular_import",
            pattern=r'^from\s+(\S+)\s+import\s+(\S+)',
            extract=lambda m: {
                "type": "circular_import",
                "module": m.group(1),
                "import": m.group(2),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "needs_verification": True
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potential circular imports", "examples": ["from module_a import ClassA"]}
        ),
        "resource_leak": QueryPattern(
            name="resource_leak",
            pattern=r'(?:open|socket\.socket)\([^)]+\)(?!\s+(?:as|with))',
            extract=lambda m: {
                "type": "resource_leak",
                "content": m.group(0),
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.85
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects potential resource leaks", "examples": ["f = open('file.txt')  # not using with"]}
        ),
        "bare_except": QueryPattern(
            name="bare_except",
            pattern=r'except\s*:',
            extract=lambda m: {
                "type": "bare_except",
                "line_number": m.string.count('\n', 0, m.start()) + 1,
                "confidence": 0.95
            },
            category=PatternCategory.COMMON_ISSUES,
            purpose=PatternPurpose.UNDERSTANDING,
            language_id=LANGUAGE_ID,
            metadata={"description": "Detects bare except clauses", "examples": ["try:\n    something()\nexcept:\n    pass"]}
        )
    }
}

class PythonPatternLearner(TreeSitterCrossProjectPatternLearner):
    """Enhanced Python pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Python-specific components."""
        await super().initialize()  # Initialize TreeSitterCrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("python", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Python patterns
        await self._pattern_processor.register_language_patterns(
            "python", 
            PYTHON_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "python_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(PYTHON_PATTERNS),
                "capabilities": list(PYTHON_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="python",
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
            
            # Finally add Python-specific patterns
            async with AsyncErrorBoundary("python_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "python",
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
                python_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(python_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "python_pattern_learner",
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
                "python_pattern_learner",
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
                "python_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "python_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_python_pattern(
    pattern: Union[TreeSitterAdaptivePattern, TreeSitterResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Python pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_tree_sitter_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Python-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("python", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "python", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_tree_sitter_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"python_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "python",
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
        await update_python_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "python_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_python_pattern_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None
) -> PatternContext:
    """Create Python-specific pattern context with tree-sitter integration.
    
    This function creates a tree-sitter based context for Python patterns
    with full system integration.
    """
    # Create a base tree-sitter context
    base_context = await create_tree_sitter_context(
        file_path,
        code_structure,
        language_id=LANGUAGE_ID,
        learned_patterns=learned_patterns
    )
    
    # Add Python-specific information
    base_context.language_stats = {"language": LANGUAGE_ID}
    base_context.relevant_patterns = list(PYTHON_PATTERNS.keys())
    
    # Add system integration metadata
    base_context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return base_context

def update_python_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_python_pattern_match_result(
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
        metadata={"language": "python"}
    )

# Initialize pattern learner
pattern_learner = PythonPatternLearner()

async def initialize_python_patterns():
    """Initialize Python patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Python patterns
    await pattern_processor.register_language_patterns(
        "python",
        PYTHON_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": PYTHON_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await PythonPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "python",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "python_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(PYTHON_PATTERNS),
            "capabilities": list(PYTHON_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "class": {
        PatternRelationType.CONTAINS: ["method", "property", "decorator"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "block", "decorator"],
        PatternRelationType.DEPENDS_ON: ["class", "module"]
    },
    "decorator": {
        PatternRelationType.CONTAINED_BY: ["class", "function", "method"],
        PatternRelationType.DEPENDS_ON: ["module"]
    },
    "import": {
        PatternRelationType.DEPENDS_ON: ["module"]
    }
}

# Export public interfaces
__all__ = [
    'PYTHON_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_python_pattern_context',
    'get_python_pattern_match_result',
    'update_python_pattern_metrics',
    'PythonPatternLearner',
    'process_python_pattern',
    'LANGUAGE_ID'
] 