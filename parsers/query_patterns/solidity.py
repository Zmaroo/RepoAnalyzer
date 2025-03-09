"""Query patterns for Solidity files.

This module provides Solidity-specific patterns with enhanced type system and relationships.
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

# Language identifier
LANGUAGE = "solidity"

# Solidity capabilities (extends common capabilities)
SOLIDITY_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SMART_CONTRACTS,
    AICapability.BLOCKCHAIN,
    AICapability.SECURITY
}

@dataclass
class SolidityPatternContext(PatternContext):
    """Solidity-specific pattern context."""
    contract_names: Set[str] = field(default_factory=set)
    function_names: Set[str] = field(default_factory=set)
    event_names: Set[str] = field(default_factory=set)
    modifier_names: Set[str] = field(default_factory=set)
    has_inheritance: bool = False
    has_modifiers: bool = False
    has_events: bool = False
    has_libraries: bool = False
    has_interfaces: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.contract_names)}:{self.has_inheritance}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "contract": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "event": PatternPerformanceMetrics(),
    "modifier": PatternPerformanceMetrics(),
    "storage": PatternPerformanceMetrics()
}

SOLIDITY_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "contract": ResilientPattern(
                pattern="""
                [
                    (contract_definition
                        name: (identifier) @syntax.contract.name
                        base: (inheritance_specifier 
                            name: (identifier) @syntax.contract.base.name)* @syntax.contract.base
                        body: (contract_body) @syntax.contract.body) @syntax.contract.def,
                    (interface_definition
                        name: (identifier) @syntax.interface.name
                        body: (contract_body) @syntax.interface.body) @syntax.interface.def,
                    (library_definition
                        name: (identifier) @syntax.library.name
                        body: (contract_body) @syntax.library.body) @syntax.library.def
                ]
                """,
                extract=lambda node: {
                    "type": "contract",
                    "name": (
                        node["captures"].get("syntax.contract.name", {}).get("text", "") or
                        node["captures"].get("syntax.interface.name", {}).get("text", "") or
                        node["captures"].get("syntax.library.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.contract.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.interface.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.library.def", {}).get("start_point", [0])[0]
                    ),
                    "is_interface": "syntax.interface.def" in node["captures"],
                    "is_library": "syntax.library.def" in node["captures"],
                    "has_inheritance": "syntax.contract.base" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "event", "modifier"],
                        PatternRelationType.DEPENDS_ON: ["contract"]
                    }
                },
                name="contract",
                description="Matches Solidity contract declarations",
                examples=["contract MyContract is BaseContract", "interface IToken", "library SafeMath"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["contract"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.func.name
                        visibility: [(public) (private) (internal) (external)] @syntax.func.visibility
                        state_mutability: [(pure) (view) (payable)] @syntax.func.mutability
                        parameters: (parameter_list) @syntax.func.params
                        return_parameters: (parameter_list)? @syntax.func.returns
                        body: (block) @syntax.func.body) @syntax.func.def,
                    (modifier_definition
                        name: (identifier) @syntax.modifier.name
                        parameters: (parameter_list)? @syntax.modifier.params
                        body: (block) @syntax.modifier.body) @syntax.modifier.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": (
                        node["captures"].get("syntax.func.name", {}).get("text", "") or
                        node["captures"].get("syntax.modifier.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.modifier.def", {}).get("start_point", [0])[0]
                    ),
                    "is_modifier": "syntax.modifier.def" in node["captures"],
                    "visibility": node["captures"].get("syntax.func.visibility", {}).get("text", ""),
                    "mutability": node["captures"].get("syntax.func.mutability", {}).get("text", ""),
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "statement"],
                        PatternRelationType.DEPENDS_ON: ["contract", "modifier"]
                    }
                },
                name="function",
                description="Matches Solidity function declarations",
                examples=["function transfer(address to, uint256 amount) public", "modifier onlyOwner"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
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
        PatternPurpose.STORAGE: {
            "storage": AdaptivePattern(
                pattern="""
                [
                    (state_variable_declaration
                        type: (type_name) @storage.var.type
                        visibility: [(public) (private) (internal)] @storage.var.visibility
                        name: (identifier) @storage.var.name
                        value: (_)? @storage.var.value) @storage.var.def,
                    (struct_declaration
                        name: (identifier) @storage.struct.name
                        members: (struct_member
                            type: (type_name) @storage.struct.member.type
                            name: (identifier) @storage.struct.member.name)* @storage.struct.members) @storage.struct.def,
                    (enum_declaration
                        name: (identifier) @storage.enum.name
                        members: (enum_value
                            name: (identifier) @storage.enum.value.name
                            value: (_)? @storage.enum.value.value)* @storage.enum.values) @storage.enum.def,
                    (mapping
                        key: (mapping_key) @storage.mapping.key
                        value: (type_name) @storage.mapping.value) @storage.mapping.def
                ]
                """,
                extract=lambda node: {
                    "type": "storage",
                    "line_number": (
                        node["captures"].get("storage.var.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.struct.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.enum.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("storage.mapping.def", {}).get("start_point", [0])[0]
                    ),
                    "name": (
                        node["captures"].get("storage.var.name", {}).get("text", "") or
                        node["captures"].get("storage.struct.name", {}).get("text", "") or
                        node["captures"].get("storage.enum.name", {}).get("text", "")
                    ),
                    "storage_type": (
                        "state_variable" if "storage.var.def" in node["captures"] else
                        "struct" if "storage.struct.def" in node["captures"] else
                        "enum" if "storage.enum.def" in node["captures"] else
                        "mapping" if "storage.mapping.def" in node["captures"] else
                        "unknown"
                    ),
                    "relationships": {
                        PatternRelationType.CONTAINED_BY: ["contract"],
                        PatternRelationType.DEPENDS_ON: ["type"]
                    }
                },
                name="storage",
                description="Matches Solidity storage declarations",
                examples=["uint256 public balance;", "struct User { address addr; }", "enum Status { Active, Inactive }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.STORAGE,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["storage"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            )
        }
    }
}

class SolidityPatternLearner(CrossProjectPatternLearner):
    """Enhanced Solidity pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with Solidity-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("solidity", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register Solidity patterns
        await self._pattern_processor.register_language_patterns(
            "solidity", 
            SOLIDITY_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "solidity_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(SOLIDITY_PATTERNS),
                "capabilities": list(SOLIDITY_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="solidity",
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
            
            # Finally add Solidity-specific patterns
            async with AsyncErrorBoundary("solidity_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "solidity",
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
                solidity_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(solidity_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "solidity_pattern_learner",
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
                "solidity_pattern_learner",
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
                "solidity_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "solidity_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_solidity_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a Solidity pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to Solidity-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("solidity", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "solidity", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_solidity_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"solidity_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "solidity",
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
        await update_solidity_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "solidity_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_solidity_pattern_context(
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
            language_id="solidity",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "solidity"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(SOLIDITY_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_solidity_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_solidity_pattern_match_result(
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
        metadata={"language": "solidity"}
    )

# Initialize pattern learner
pattern_learner = SolidityPatternLearner()

async def initialize_solidity_patterns():
    """Initialize Solidity patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register Solidity patterns
    await pattern_processor.register_language_patterns(
        "solidity",
        SOLIDITY_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": SOLIDITY_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await SolidityPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "solidity",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "solidity_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(SOLIDITY_PATTERNS),
            "capabilities": list(SOLIDITY_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "contract": {
        PatternRelationType.CONTAINS: ["function", "event", "modifier"],
        PatternRelationType.DEPENDS_ON: ["contract"]
    },
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "statement"],
        PatternRelationType.DEPENDS_ON: ["contract", "modifier"]
    },
    "storage": {
        PatternRelationType.CONTAINED_BY: ["contract"],
        PatternRelationType.DEPENDS_ON: ["type"]
    }
}

# Export public interfaces
__all__ = [
    'SOLIDITY_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_solidity_pattern_match_result',
    'update_solidity_pattern_metrics',
    'SolidityPatternContext',
    'pattern_learner'
] 