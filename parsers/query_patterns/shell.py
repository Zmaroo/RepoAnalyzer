"""Query patterns for Shell files.

This module provides Shell-specific patterns with enhanced type system and relationships.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, PatternType,
    PatternRelationType, PatternContext, PatternPerformanceMetrics
)
from parsers.query_patterns.enhanced_patterns import (
    ResilientPattern, AdaptivePattern, CrossProjectPatternLearner
)
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.logger import log

# Language identifier
LANGUAGE = "shell"

@dataclass
class ShellPatternContext(PatternContext):
    """Shell-specific pattern context."""
    function_names: Set[str] = field(default_factory=set)
    variable_names: Set[str] = field(default_factory=set)
    alias_names: Set[str] = field(default_factory=set)
    has_functions: bool = False
    has_arrays: bool = False
    has_pipes: bool = False
    has_redirects: bool = False
    has_subshells: bool = False
    
    def get_context_key(self) -> str:
        """Generate unique context key."""
        return f"{super().get_context_key()}:{len(self.function_names)}:{self.has_functions}"

# Initialize pattern metrics
PATTERN_METRICS = {
    "function": PatternPerformanceMetrics(),
    "variable": PatternPerformanceMetrics(),
    "command": PatternPerformanceMetrics(),
    "pipeline": PatternPerformanceMetrics(),
    "redirect": PatternPerformanceMetrics()
}

SHELL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": ResilientPattern(
                pattern="""
                [
                    (function_definition
                        name: (word) @syntax.func.name
                        body: (compound_statement) @syntax.func.body) @syntax.func.def,
                    (function_definition
                        name: (word) @syntax.func.name
                        body: (group) @syntax.func.group) @syntax.func.group.def
                ]
                """,
                extract=lambda node: {
                    "type": "function",
                    "name": node["captures"].get("syntax.func.name", {}).get("text", ""),
                    "line_number": node["captures"].get("syntax.func.def", {}).get("start_point", [0])[0],
                    "is_grouped": "syntax.func.group.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.CONTAINS: ["command", "variable", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["function"]
                    }
                },
                name="function",
                description="Matches Shell function declarations",
                examples=["function process() { echo 'done'; }", "backup() ( tar -czf backup.tar.gz . )"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["function"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                    }
                }
            ),
            "variable": ResilientPattern(
                pattern="""
                [
                    (variable_assignment
                        name: (variable_name) @syntax.var.name
                        value: (_) @syntax.var.value) @syntax.var.def,
                    (array_assignment
                        name: (variable_name) @syntax.array.name
                        elements: (array) @syntax.array.elements) @syntax.array.def
                ]
                """,
                extract=lambda node: {
                    "type": "variable",
                    "name": (
                        node["captures"].get("syntax.var.name", {}).get("text", "") or
                        node["captures"].get("syntax.array.name", {}).get("text", "")
                    ),
                    "line_number": (
                        node["captures"].get("syntax.var.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("syntax.array.def", {}).get("start_point", [0])[0]
                    ),
                    "is_array": "syntax.array.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.REFERENCED_BY: ["command", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["variable"]
                    }
                },
                name="variable",
                description="Matches Shell variable assignments",
                examples=["NAME='value'", "ARRAY=(one two three)"],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id=LANGUAGE,
                confidence=0.95,
                metadata={
                    "metrics": PATTERN_METRICS["variable"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[A-Z_][A-Z0-9_]*$'
                    }
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.COMMANDS: {
            "command": AdaptivePattern(
                pattern="""
                [
                    (command
                        name: (command_name) @cmd.name
                        argument: (_)* @cmd.args) @cmd.def,
                    (pipeline
                        command: (command)+ @cmd.pipe.command) @cmd.pipe.def,
                    (subshell
                        command: (_) @cmd.sub.command) @cmd.sub.def
                ]
                """,
                extract=lambda node: {
                    "type": "command",
                    "name": node["captures"].get("cmd.name", {}).get("text", ""),
                    "line_number": node["captures"].get("cmd.def", {}).get("start_point", [0])[0],
                    "is_pipeline": "cmd.pipe.def" in node["captures"],
                    "is_subshell": "cmd.sub.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.USES: ["variable", "function"],
                        PatternRelationType.DEPENDS_ON: ["command"]
                    }
                },
                name="command",
                description="Matches Shell command executions",
                examples=["ls -la", "echo $PATH | grep bin", "( cd /tmp && ls )"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.COMMANDS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["command"],
                    "validation": {
                        "required_fields": ["name"],
                        "name_format": r'^[a-zA-Z0-9_.-]+$'
                    }
                }
            )
        },
        PatternPurpose.REDIRECTS: {
            "redirect": AdaptivePattern(
                pattern="""
                [
                    (redirected_statement
                        command: (_) @redir.command
                        redirect: (file_redirect
                            descriptor: (_)? @redir.fd
                            operator: (_) @redir.op
                            file: (_) @redir.file)) @redir.def,
                    (heredoc_redirect
                        start: (_) @redir.heredoc.start
                        content: (_) @redir.heredoc.content
                        end: (_) @redir.heredoc.end) @redir.heredoc.def
                ]
                """,
                extract=lambda node: {
                    "type": "redirect",
                    "line_number": (
                        node["captures"].get("redir.def", {}).get("start_point", [0])[0] or
                        node["captures"].get("redir.heredoc.def", {}).get("start_point", [0])[0]
                    ),
                    "operator": node["captures"].get("redir.op", {}).get("text", ""),
                    "is_heredoc": "redir.heredoc.def" in node["captures"],
                    "relationships": {
                        PatternRelationType.MODIFIES: ["command", "pipeline"],
                        PatternRelationType.DEPENDS_ON: ["file"]
                    }
                },
                name="redirect",
                description="Matches Shell redirections",
                examples=["command > output.txt", "cat << EOF", "2>&1"],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.REDIRECTS,
                language_id=LANGUAGE,
                confidence=0.9,
                metadata={
                    "metrics": PATTERN_METRICS["redirect"],
                    "validation": {
                        "required_fields": [],
                        "name_format": None
                    }
                }
            )
        }
    }
}

# Initialize pattern learner
pattern_learner = CrossProjectPatternLearner()

async def extract_shell_patterns_for_learning(content: str) -> List[Dict[str, Any]]:
    """Extract patterns from Shell content for repository learning."""
    patterns = []
    context = ShellPatternContext()
    
    try:
        # Process each pattern category
        for category in PatternCategory:
            if category in SHELL_PATTERNS:
                category_patterns = SHELL_PATTERNS[category]
                for purpose in category_patterns:
                    for pattern_name, pattern in category_patterns[purpose].items():
                        if isinstance(pattern, (ResilientPattern, AdaptivePattern)):
                            try:
                                matches = await pattern.matches(content, context)
                                for match in matches:
                                    patterns.append({
                                        "name": pattern_name,
                                        "category": category.value,
                                        "purpose": purpose.value,
                                        "content": match.get("text", ""),
                                        "metadata": match,
                                        "confidence": pattern.confidence,
                                        "relationships": match.get("relationships", {})
                                    })
                                    
                                    # Update context
                                    if match["type"] == "function":
                                        context.function_names.add(match["name"])
                                        context.has_functions = True
                                    elif match["type"] == "variable":
                                        context.variable_names.add(match["name"])
                                        if match["is_array"]:
                                            context.has_arrays = True
                                    elif match["type"] == "command":
                                        if match["is_pipeline"]:
                                            context.has_pipes = True
                                        if match["is_subshell"]:
                                            context.has_subshells = True
                                    elif match["type"] == "redirect":
                                        context.has_redirects = True
                                    
                            except Exception as e:
                                await log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                continue
    
    except Exception as e:
        await log(f"Error extracting Shell patterns: {e}", level="error")
    
    return patterns

# Metadata for pattern relationships
PATTERN_RELATIONSHIPS = {
    "function": {
        PatternRelationType.CONTAINS: ["command", "variable", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["function"]
    },
    "variable": {
        PatternRelationType.REFERENCED_BY: ["command", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["variable"]
    },
    "command": {
        PatternRelationType.USES: ["variable", "function"],
        PatternRelationType.DEPENDS_ON: ["command"]
    },
    "redirect": {
        PatternRelationType.MODIFIES: ["command", "pipeline"],
        PatternRelationType.DEPENDS_ON: ["file"]
    }
}

# Export public interfaces
__all__ = [
    'SHELL_PATTERNS',
    'PATTERN_RELATIONSHIPS',
    'extract_shell_patterns_for_learning',
    'ShellPatternContext',
    'pattern_learner'
] 