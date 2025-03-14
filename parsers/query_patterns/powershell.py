"""Query patterns for PowerShell files.

This module provides PowerShell-specific patterns with enhanced type system and relationships.
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
LANGUAGE = "powershell"

# PowerShell capabilities (extends common capabilities)
POWERSHELL_CAPABILITIES = COMMON_CAPABILITIES | {
    AICapability.SCRIPTING,
    AICapability.AUTOMATION,
    AICapability.REMOTE_MANAGEMENT
}

@dataclass
class PowerShellPatternContext(PatternContext):
    """PowerShell-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    class_names: Set[str] = field(default_factory=set)
    pipeline_commands: Set[str] = field(default_factory=set)
    has_inheritance: bool = False
    has_modifiers: bool = False
    has_events: bool = False
    has_libraries: bool = False
    has_error_handling: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_error_handling}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "class": PatternPerformanceMetrics(),
    "pipeline": PatternPerformanceMetrics(),
    "exception": PatternPerformanceMetrics()
}

# Convert existing patterns to enhanced patterns
POWERSHELL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_statement
                        name: (identifier) @syntax.function.name
                        parameters: (param_block)? @syntax.function.params
                        body: (script_block) @syntax.function.body) @syntax.function.def,
                    (filter_statement
                        name: (identifier) @syntax.filter.name
                        parameters: (param_block)? @syntax.filter.params
                        body: (script_block) @syntax.filter.body) @syntax.filter.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function" if "syntax.function.def" in node["captures"] else "filter",
                    "line_number": node["captures"].get("syntax.function.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["parameter", "statement"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="function",
                description="Matches PowerShell function declarations",
                examples=["function Get-Item {}", "filter Process-Item {}"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            ),
            "class": ResilientPattern(
                pattern="""
                [
                    (class_statement
                        name: (identifier) @syntax.class.name
                        base: (base_class)? @syntax.class.base
                        body: (class_body) @syntax.class.body) @syntax.class.def,
                    (enum_statement
                        name: (identifier) @syntax.enum.name
                        body: (enum_body) @syntax.enum.body) @syntax.enum.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", "") or
                           node["captures"].get("syntax.enum.name", {}).get("text", ""),
                    "type": "class" if "syntax.class.def" in node["captures"] else "enum",
                    "line_number": node["captures"].get("syntax.class.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["function", "property"],
                        PatternRelationType.DEPENDS_ON: ["class"]
                    }
                },
                name="class",
                description="Matches PowerShell class declarations",
                examples=["class MyClass {}", "enum MyEnum {}"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["class"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "pipeline": ResilientPattern(
                pattern="""
                [
                    (pipeline
                        (command
                            name: (command_name) @structure.pipeline.cmd.name
                            arguments: (command_elements)? @structure.pipeline.cmd.args) @structure.pipeline.cmd) @structure.pipeline,
                    (pipeline
                        (command
                            name: (command_name_expr) @structure.pipeline.expr.name
                            arguments: (command_elements)? @structure.pipeline.expr.args) @structure.pipeline.expr) @structure.pipeline
                ]
                """,
                extract=lambda node: {
                    "command": node["captures"].get("structure.pipeline.cmd.name", {}).get("text", "") or
                              node["captures"].get("structure.pipeline.expr.name", {}).get("text", ""),
                    "type": "pipeline",
                    "line_number": node["captures"].get("structure.pipeline.cmd.def", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["command"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="pipeline",
                description="Matches PowerShell pipeline declarations",
                examples=["pipeline Get-Item -Filter *"],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["pipeline"],
                    "validation": {
                        "required_fields": ["command"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$'
                    }
                }
            ),
            "exception": ResilientPattern(
                pattern="""
                [
                    (try_statement
                        body: (statement_block) @structure.exception.try
                        catch: (catch_clauses)? @structure.exception.catch
                        finally: (finally_clause)? @structure.exception.finally) @structure.exception.try,
                    (trap_statement
                        type: (type_literal) @structure.exception.trap.type
                        body: (statement_block) @structure.exception.trap.body) @structure.exception.trap
                ]
                """,
                extract=lambda node: {
                    "type": "try_catch" if "structure.exception.try" in node["captures"] else "trap",
                    "has_finally": "structure.exception.finally" in node["captures"],
                    "line_number": node["captures"].get("structure.exception.try", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["statement"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="exception",
                description="Matches PowerShell exception handling declarations",
                examples=["try { ... } catch { ... }", "trap { ... }"],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["exception"],
                    "validation": {
                        "required_fields": ["type"],
                        "type_format": r'^(try_catch|trap)$'
                    }
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": ResilientPattern(
                pattern="""
                [
                    (comment) @documentation.comment,
                    (comment) @documentation.help {
                        match: "^\\.SYNOPSIS|^\\.DESCRIPTION|^\\.PARAMETER|^\\.EXAMPLE|^\\.NOTES"
                    }
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.comment", {}).get("text", ""),
                    "is_help": "documentation.help" in node["captures"],
                    "line_number": node["captures"].get("documentation.comment", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["text"],
                        PatternRelationType.DEPENDS_ON: ["comment"]
                    }
                },
                name="comment",
                description="Matches PowerShell comment declarations",
                examples=["# This is a comment", ".SYNOPSIS"],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["comment"],
                    "validation": {
                        "required_fields": ["text"],
                        "text_format": r'^.*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "script_structure": ResilientPattern(
                pattern="""
                [
                    (function_statement
                        name: (identifier) @script.func.name
                        parameters: (param_block)? @script.func.params
                        body: (script_block) @script.func.body) @script.func,
                        
                    (class_statement
                        name: (identifier) @script.class.name
                        base: (base_class)? @script.class.base
                        body: (class_body) @script.class.body) @script.class,
                        
                    (param_statement
                        parameters: (parameter_list) @script.param.list) @script.param,
                        
                    (using_statement
                        namespace: (_) @script.using.namespace) @script.using,
                        
                    (begin_block) @script.begin,
                    (process_block) @script.process,
                    (end_block) @script.end
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "script_structure",
                    "is_function": "script.func" in node["captures"],
                    "is_class": "script.class" in node["captures"],
                    "has_param_block": "script.param" in node["captures"],
                    "has_using_statement": "script.using" in node["captures"],
                    "has_begin_block": "script.begin" in node["captures"],
                    "has_process_block": "script.process" in node["captures"],
                    "has_end_block": "script.end" in node["captures"],
                    "function_name": node["captures"].get("script.func.name", {}).get("text", ""),
                    "class_name": node["captures"].get("script.class.name", {}).get("text", ""),
                    "base_class": node["captures"].get("script.class.base", {}).get("text", ""),
                    "imported_namespace": node["captures"].get("script.using.namespace", {}).get("text", ""),
                    "param_count": len((node["captures"].get("script.param.list", {}).get("text", "") or "").split(","))
                },
                name="script_structure",
                description="Matches PowerShell script structure declarations",
                examples=["function Get-Item {}", "class MyClass {}"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.BEST_PRACTICES,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["script_structure"],
                    "validation": {
                        "required_fields": ["pattern_type", "is_function", "is_class", "has_param_block", "has_using_statement", "has_begin_block", "has_process_block", "has_end_block", "function_name", "class_name", "base_class", "imported_namespace", "param_count"],
                        "pattern_type_format": r'^script_structure$',
                        "is_function_format": r'^(True|False)$',
                        "is_class_format": r'^(True|False)$',
                        "has_param_block_format": r'^(True|False)$',
                        "has_using_statement_format": r'^(True|False)$',
                        "has_begin_block_format": r'^(True|False)$',
                        "has_process_block_format": r'^(True|False)$',
                        "has_end_block_format": r'^(True|False)$',
                        "function_name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$',
                        "class_name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$',
                        "base_class_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$',
                        "imported_namespace_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$',
                        "param_count_format": r'^[0-9]+$'
                    }
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "pipeline_patterns": ResilientPattern(
                pattern="""
                [
                    (pipeline
                        (command
                            name: (command_name) @pipe.cmd.name
                            arguments: (command_elements)? @pipe.cmd.args)) @pipe.single,
                            
                    (pipeline
                        (command) @pipe.first
                        (command) @pipe.second) @pipe.multi,
                        
                    (pipeline
                        (command
                            name: (command_name) @pipe.where.cmd
                            (#match? @pipe.where.cmd "^Where-Object$|^where$|^?$")
                            arguments: (command_elements) @pipe.where.args)) @pipe.where,
                            
                    (pipeline
                        (command
                            name: (command_name) @pipe.select.cmd
                            (#match? @pipe.select.cmd "^Select-Object$|^select$"))) @pipe.select
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "pipeline_usage",
                    "is_single_command": "pipe.single" in node["captures"] and not ("pipe.multi" in node["captures"]),
                    "is_pipeline": "pipe.multi" in node["captures"],
                    "uses_where_filter": "pipe.where" in node["captures"],
                    "uses_select_projection": "pipe.select" in node["captures"],
                    "command_name": node["captures"].get("pipe.cmd.name", {}).get("text", ""),
                    "pipeline_length": 2 if "pipe.multi" in node["captures"] else 1 if "pipe.single" in node["captures"] else 0,
                    "filter_condition": node["captures"].get("pipe.where.args", {}).get("text", ""),
                    "uses_common_verbs": any(
                        verb in (node["captures"].get("pipe.cmd.name", {}).get("text", "") or "")
                        for verb in ["Get-", "Set-", "New-", "Remove-", "Add-", "Import-", "Export-"]
                    )
                },
                name="pipeline_patterns",
                description="Matches PowerShell pipeline usage declarations",
                examples=["pipeline Get-Item -Filter *", "pipeline Get-Process -Name *"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.CODE_ORGANIZATION,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["pipeline_patterns"],
                    "validation": {
                        "required_fields": ["pattern_type", "is_single_command", "is_pipeline", "uses_where_filter", "uses_select_projection", "command_name", "pipeline_length", "filter_condition", "uses_common_verbs"],
                        "pattern_type_format": r'^pipeline_usage$',
                        "is_single_command_format": r'^(True|False)$',
                        "is_pipeline_format": r'^(True|False)$',
                        "uses_where_filter_format": r'^(True|False)$',
                        "uses_select_projection_format": r'^(True|False)$',
                        "command_name_format": r'^[a-zA-Z_][a-zA-Z0-9_-]*$',
                        "pipeline_length_format": r'^[0-9]+$',
                        "filter_condition_format": r'^.*$',
                        "uses_common_verbs_format": r'^(True|False)$'
                    }
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "error_handling": ResilientPattern(
                pattern="""
                [
                    (try_statement
                        body: (statement_block) @error.try.body
                        catch: (catch_clauses)? @error.try.catch
                        finally: (finally_clause)? @error.try.finally) @error.try,
                        
                    (trap_statement
                        type: (type_literal) @error.trap.type
                        body: (statement_block) @error.trap.body) @error.trap,
                        
                    (command
                        name: (command_name) @error.cmd.name
                        (#match? @error.cmd.name "^Write-Error$|^throw$")
                        arguments: (command_elements)? @error.cmd.args) @error.cmd,
                        
                    (pipeline_operator) @error.silent {
                        match: "^2>"
                    }
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "error_handling",
                    "is_try_catch": "error.try" in node["captures"],
                    "is_trap": "error.trap" in node["captures"],
                    "is_write_error": "error.cmd" in node["captures"] and "Write-Error" in (node["captures"].get("error.cmd.name", {}).get("text", "") or ""),
                    "is_throw": "error.cmd" in node["captures"] and "throw" in (node["captures"].get("error.cmd.name", {}).get("text", "") or ""),
                    "uses_redirection": "error.silent" in node["captures"],
                    "exception_type": node["captures"].get("error.trap.type", {}).get("text", ""),
                    "has_finally": "error.try.finally" in node["captures"],
                    "error_handling_style": (
                        "try_catch" if "error.try" in node["captures"] else
                        "trap" if "error.trap" in node["captures"] else
                        "command" if "error.cmd" in node["captures"] else
                        "redirection" if "error.silent" in node["captures"] else
                        "unspecified"
                    ),
                    "line_number": node["captures"].get("error.try", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["statement"],
                        PatternRelationType.DEPENDS_ON: ["function", "pipeline"]
                    }
                },
                name="error_handling",
                description="Matches PowerShell error handling declarations",
                examples=["try { ... } catch { ... }", "trap { ... }"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.ERROR_HANDLING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["error_handling"],
                    "validation": {
                        "required_fields": ["pattern_type", "is_try_catch", "is_trap", "is_write_error", "is_throw", "uses_redirection", "exception_type", "has_finally", "error_handling_style"],
                        "pattern_type_format": r'^(try_catch|trap|command|redirection|unspecified)$',
                        "is_try_catch_format": r'^(True|False)$',
                        "is_trap_format": r'^(True|False)$',
                        "is_write_error_format": r'^(True|False)$',
                        "is_throw_format": r'^(True|False)$',
                        "uses_redirection_format": r'^(True|False)$',
                        "exception_type_format": r'^.*$',
                        "has_finally_format": r'^(True|False)$',
                        "error_handling_style_format": r'^(try_catch|trap|command|redirection|unspecified)$'
                    }
                }
            )
        },
        PatternPurpose.REMOTE_MANAGEMENT: {
            "remote_management": ResilientPattern(
                pattern="""
                [
                    (command
                        name: (command_name) @remote.cmd.name
                        (#match? @remote.cmd.name "^Invoke-Command$|^Enter-PSSession$|^New-PSSession$|^Remove-PSSession$|^icm$")
                        arguments: (command_elements) @remote.cmd.args) @remote.cmd,
                        
                    (command
                        arguments: (command_elements
                            (command_parameter
                                name: (command_parameter_name) @remote.param.name
                                (#match? @remote.param.name "^-ComputerName$|^-Session$|^-VMName$|^-ContainerName$")))) @remote.param,
                                
                    (command
                        name: (command_name) @remote.wsman.name
                        (#match? @remote.wsman.name "^New-WSManSessionOption$|^Connect-WSMan$|^Disconnect-WSMan$")) @remote.wsman,
                        
                    (command
                        name: (command_name) @remote.cim.name
                        (#match? @remote.cim.name "^Get-CimInstance$|^New-CimSession$|^Invoke-CimMethod$")) @remote.cim
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "remote_management",
                    "uses_invoke_command": "remote.cmd" in node["captures"] and "Invoke-Command" in (node["captures"].get("remote.cmd.name", {}).get("text", "") or ""),
                    "uses_ps_session": "remote.cmd" in node["captures"] and any(
                        session in (node["captures"].get("remote.cmd.name", {}).get("text", "") or "")
                        for session in ["Enter-PSSession", "New-PSSession", "Remove-PSSession"]
                    ),
                    "uses_remote_parameter": "remote.param" in node["captures"],
                    "uses_wsman": "remote.wsman" in node["captures"],
                    "uses_cim": "remote.cim" in node["captures"],
                    "remote_parameter": node["captures"].get("remote.param.name", {}).get("text", ""),
                    "remote_style": (
                        "pssession" if (
                            "remote.cmd" in node["captures"] and 
                            any(session in (node["captures"].get("remote.cmd.name", {}).get("text", "") or "")
                                for session in ["Enter-PSSession", "New-PSSession", "Remove-PSSession"])
                        ) else
                        "invoke_command" if (
                            "remote.cmd" in node["captures"] and 
                            "Invoke-Command" in (node["captures"].get("remote.cmd.name", {}).get("text", "") or "")
                        ) else
                        "wsman" if "remote.wsman" in node["captures"] else
                        "cim" if "remote.cim" in node["captures"] else
                        "parameter" if "remote.param" in node["captures"] else
                        "none"
                    ),
                    "line_number": node["captures"].get("remote.cmd", {}).get("start_point", [0])[0],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["command"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="remote_management",
                description="Matches PowerShell remote management declarations",
                examples=["Invoke-Command -ScriptBlock { ... }", "Enter-PSSession -ComputerName *"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REMOTE_MANAGEMENT,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["remote_management"],
                    "validation": {
                        "required_fields": ["pattern_type", "uses_invoke_command", "uses_ps_session", "uses_remote_parameter", "uses_wsman", "uses_cim", "remote_parameter", "remote_style"],
                        "pattern_type_format": r'^(pssession|invoke_command|wsman|cim|parameter|none)$',
                        "uses_invoke_command_format": r'^(True|False)$',
                        "uses_ps_session_format": r'^(True|False)$',
                        "uses_remote_parameter_format": r'^(True|False)$',
                        "uses_wsman_format": r'^(True|False)$',
                        "uses_cim_format": r'^(True|False)$',
                        "remote_parameter_format": r'^.*$',
                        "remote_style_format": r'^(pssession|invoke_command|wsman|cim|parameter|none)$'
                    }
                }
            )
        }
    }
}

class PowerShellPatternLearner(CrossProjectPatternLearner):
    """Enhanced PowerShell pattern learner with cross-project learning capabilities."""
    
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
        """Initialize with PowerShell-specific components."""
        await super().initialize()  # Initialize CrossProjectPatternLearner components
        
        # Initialize core components
        self._block_extractor = await get_block_extractor()
        self._feature_extractor = await BaseFeatureExtractor.create("powershell", FileType.CODE)
        self._unified_parser = await get_unified_parser()
        self._ai_processor = await get_ai_pattern_processor()
        
        # Register PowerShell patterns
        await self._pattern_processor.register_language_patterns(
            "powershell", 
            POWERSHELL_PATTERNS,
            self
        )
        
        # Initialize health monitoring
        await global_health_monitor.update_component_status(
            "powershell_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": len(POWERSHELL_PATTERNS),
                "capabilities": list(POWERSHELL_CAPABILITIES)
            }
        )

    async def learn_from_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Learn patterns with cross-project and AI assistance."""
        start_time = time.time()
        self._metrics["total_patterns"] += 1
        
        try:
            # First try AI-assisted learning
            ai_context = AIContext(
                language_id="powershell",
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
            
            # Finally add PowerShell-specific patterns
            async with AsyncErrorBoundary("powershell_pattern_learning"):
                # Extract blocks with caching
                blocks = await self._block_extractor.get_child_blocks(
                    "powershell",
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
                powershell_patterns = await self._learn_patterns_from_features(features)
                learned_patterns.extend(powershell_patterns)
            
            # Update metrics
            learning_time = time.time() - start_time
            self._metrics["learning_times"].append(learning_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                "powershell_pattern_learner",
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
                "powershell_pattern_learner",
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
                "powershell_pattern_learner",
                ComponentStatus.SHUTDOWN,
                details={
                    "cleanup": "successful",
                    "final_metrics": self._metrics
                }
            )
            
        except Exception as e:
            await log(f"Error in cleanup: {e}", level="error")
            await global_health_monitor.update_component_status(
                "powershell_pattern_learner",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

@handle_async_errors(error_types=ProcessingError)
async def process_powershell_pattern(
    pattern: Union[AdaptivePattern, ResilientPattern],
    source_code: str,
    context: Optional[PatternContext] = None
) -> List[Dict[str, Any]]:
    """Process a PowerShell pattern with full system integration."""
    # First try common pattern processing
    common_result = await process_common_pattern(pattern, source_code, context)
    if common_result:
        return common_result
    
    # Fall back to PowerShell-specific processing
    async with AsyncErrorBoundary(
        operation_name=f"process_pattern_{pattern.name}",
        error_types=ProcessingError,
        severity=ErrorSeverity.ERROR
    ):
        # Get all required components
        block_extractor = await get_block_extractor()
        feature_extractor = await BaseFeatureExtractor.create("powershell", FileType.CODE)
        unified_parser = await get_unified_parser()
        
        # Parse if needed
        if not context or not context.code_structure:
            parse_result = await unified_parser.parse(source_code, "powershell", FileType.CODE)
            if parse_result and parse_result.ast:
                context = await create_powershell_pattern_context(
                    "",
                    parse_result.ast
                )
        
        # Extract and process blocks with caching
        cache_key = f"powershell_pattern_{pattern.name}_{hash(source_code)}"
        cached_result = await get_current_request_cache().get(cache_key)
        if cached_result:
            return cached_result
        
        blocks = await block_extractor.get_child_blocks(
            "powershell",
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
        await update_powershell_pattern_metrics(
            pattern.name,
            {
                "execution_time": time.time() - start_time,
                "matches": len(matches)
            }
        )
        
        # Update health status
        await global_health_monitor.update_component_status(
            "powershell_pattern_processor",
            ComponentStatus.HEALTHY,
            details={
                "pattern": pattern.name,
                "matches": len(matches),
                "processing_time": time.time() - start_time
            }
        )
        
        return matches

async def create_powershell_pattern_context(
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
            language_id="powershell",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "powershell"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        dependencies=set(),
        recent_changes=[],
        scope_level="global",
        allows_nesting=True,
        relevant_patterns=list(POWERSHELL_PATTERNS.keys())
    )
    
    # Add system integration metadata
    context.metadata.update({
        "parser_type": ParserType.TREE_SITTER,
        "feature_extraction_enabled": True,
        "block_extraction_enabled": True,
        "pattern_learning_enabled": True
    })
    
    return context

def update_powershell_pattern_metrics(pattern_name: str, metrics: Dict[str, Any]) -> None:
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

def get_powershell_pattern_match_result(
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
        metadata={"language": "powershell"}
    )

# Initialize pattern learner
pattern_learner = PowerShellPatternLearner()

async def initialize_powershell_patterns():
    """Initialize PowerShell patterns during app startup."""
    global pattern_learner
    
    # Initialize pattern processor first
    await pattern_processor.initialize()
    
    # Register PowerShell patterns
    await pattern_processor.register_language_patterns(
        "powershell",
        POWERSHELL_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": POWERSHELL_CAPABILITIES
        }
    )
    
    # Create and initialize learner
    pattern_learner = await PowerShellPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "powershell",
        pattern_learner
    )
    
    await global_health_monitor.update_component_status(
        "powershell_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": len(POWERSHELL_PATTERNS),
            "capabilities": list(POWERSHELL_CAPABILITIES)
        }
    )

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["parameter", "statement"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "class": {
        PatternRelationType.CONTAINS: ["function", "property"],
        PatternRelationType.DEPENDS_ON: ["class"]
    },
    "pipeline": {
        PatternRelationType.CONTAINS: ["command"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "error_handling": {
        PatternRelationType.CONTAINS: ["statement"],
        PatternRelationType.DEPENDS_ON: ["function", "pipeline"]
    }
}

# Export public interfaces
__all__ = [
    'POWERSHELL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'PATTERN_METRICS',
    'create_pattern_context',
    'get_powershell_pattern_match_result',
    'update_powershell_pattern_metrics',
    'PowerShellPatternContext',
    'pattern_learner'
] 