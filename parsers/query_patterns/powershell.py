"""Query patterns for PowerShell files."""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

POWERSHELL_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
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
                    "type": "function" if "syntax.function.def" in node["captures"] else "filter"
                }
            ),
            "class": QueryPattern(
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
                    "type": "class" if "syntax.class.def" in node["captures"] else "enum"
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "pipeline": QueryPattern(
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
                    "type": "pipeline"
                }
            ),
            "exception": QueryPattern(
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
                    "has_finally": "structure.exception.finally" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "comment": QueryPattern(
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
                    "is_help": "documentation.help" in node["captures"]
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.BEST_PRACTICES: {
            "script_structure": QueryPattern(
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
                }
            )
        },
        PatternPurpose.CODE_ORGANIZATION: {
            "pipeline_patterns": QueryPattern(
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
                }
            )
        },
        PatternPurpose.ERROR_HANDLING: {
            "error_handling": QueryPattern(
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
                    )
                }
            )
        },
        PatternPurpose.REMOTE_MANAGEMENT: {
            "remote_management": QueryPattern(
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
                    )
                }
            )
        }
    }
} 