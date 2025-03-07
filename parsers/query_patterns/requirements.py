"""
Query patterns for requirements.txt files.

These patterns target the 'package' nodes extracted from a requirements file.
"""
from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

REQUIREMENTS_PATTERNS_FOR_LEARNING = {
    "dependency_specifications": {
        "pattern": """
        [
            (requirement
                package: (package) @dep.pkg.name
                version_spec: (version_spec
                    version_cmp: (version_cmp) @dep.pkg.cmp
                    version: (version) @dep.pkg.version)? @dep.pkg.version_spec
                extras: (extras
                    package: (package)* @dep.pkg.extras.package)? @dep.pkg.extras) @dep.pkg,
                
            (requirement
                package: (package) @direct.url.pkg
                url_spec: (url_spec) @direct.url.spec) @direct.url,
                
            (requirement
                package: (package) @local.pkg
                path_spec: (path_spec) @local.path) @local.req
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "dependency_specifications",
            "is_versioned_package": "dep.pkg" in node["captures"],
            "is_direct_url": "direct.url" in node["captures"],
            "is_local_path": "local.req" in node["captures"],
            "package_name": node["captures"].get("dep.pkg.name", {}).get("text", "") or 
                          node["captures"].get("direct.url.pkg", {}).get("text", "") or
                          node["captures"].get("local.pkg", {}).get("text", ""),
            "version_comparison": node["captures"].get("dep.pkg.cmp", {}).get("text", ""),
            "version": node["captures"].get("dep.pkg.version", {}).get("text", ""),
            "has_extras": "dep.pkg.extras" in node["captures"] and node["captures"].get("dep.pkg.extras", {}).get("text", ""),
            "dependency_type": (
                "versioned_package" if "dep.pkg" in node["captures"] else
                "direct_url" if "direct.url" in node["captures"] else
                "local_path" if "local.req" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "constraint_patterns": {
        "pattern": """
        [
            (requirement
                marker_spec: (marker_spec
                    marker_var: (marker_var) @constraint.var
                    marker_op: (marker_op) @constraint.op
                    marker_value: [(quoted_string) (marker_var)] @constraint.value) @constraint.spec) @constraint.req,
                    
            (requirement
                version_spec: (version_spec
                    version_cmp: [(version_cmp) (version_cmp_multi)] @version.constraint.op
                    version: (version) @version.constraint.value) @version.constraint) @version.req
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "constraint_patterns",
            "is_environment_marker": "constraint.req" in node["captures"],
            "is_version_constraint": "version.req" in node["captures"],
            "marker_variable": node["captures"].get("constraint.var", {}).get("text", ""),
            "marker_operator": node["captures"].get("constraint.op", {}).get("text", ""),
            "marker_value": node["captures"].get("constraint.value", {}).get("text", ""),
            "version_operator": node["captures"].get("version.constraint.op", {}).get("text", ""),
            "version_value": node["captures"].get("version.constraint.value", {}).get("text", ""),
            "constraint_type": (
                "environment_marker" if "constraint.req" in node["captures"] else
                "version_constraint" if "version.req" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "file_organization": {
        "pattern": """
        [
            (file
                [(requirement) (global_opt) (comment) (path) (url)]* @file.content) @file.def,
                
            (comment
                text: /^#.*dependencies.*$/i) @comment.section,
                
            (linebreak
                comment: (comment) @linebreak.comment.text) @linebreak.comment,
                
            (blank_line) @blank
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "file_organization",
            "is_file": "file.def" in node["captures"],
            "is_section_comment": "comment.section" in node["captures"],
            "is_inline_comment": "linebreak.comment" in node["captures"],
            "is_blank_line": "blank" in node["captures"],
            "comment_text": node["captures"].get("comment.section", {}).get("text", "") or 
                          node["captures"].get("linebreak.comment.text", {}).get("text", ""),
            "file_structure_type": (
                "structured_with_comments" if ("comment.section" in node["captures"] or "linebreak.comment" in node["captures"]) else
                "basic_requirements" if "file.def" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "option_patterns": {
        "pattern": """
        [
            (global_opt
                option: (option) @global.opt.name
                value: [(argument) (quoted_string) (path) (url)]* @global.opt.value) @global.opt,
                
            (requirement_opt
                option: (option) @req.opt.name
                value: [(argument) (quoted_string)] @req.opt.value) @req.opt
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "option_patterns",
            "is_global_option": "global.opt" in node["captures"],
            "is_requirement_option": "req.opt" in node["captures"],
            "option_name": node["captures"].get("global.opt.name", {}).get("text", "") or 
                         node["captures"].get("req.opt.name", {}).get("text", ""),
            "option_value": node["captures"].get("global.opt.value", {}).get("text", "") or 
                          node["captures"].get("req.opt.value", {}).get("text", ""),
            "option_type": (
                "global" if "global.opt" in node["captures"] else
                "requirement_specific" if "req.opt" in node["captures"] else
                "unknown"
            )
        }
    }
}

REQUIREMENTS_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "requirement": QueryPattern(
                pattern="""
                [
                    (requirement
                        package: (package) @syntax.requirement.name
                        version_spec: (version_spec
                            version_cmp: (version_cmp) @syntax.requirement.version.operator
                            version: (version) @syntax.requirement.version.number)? @syntax.requirement.version
                        extras: (extras
                            package: (package)* @syntax.requirement.extras.package)? @syntax.requirement.extras
                        marker_spec: (marker_spec
                            marker_var: (marker_var) @syntax.requirement.marker.var
                            marker_op: (marker_op) @syntax.requirement.marker.op
                            (quoted_string)? @syntax.requirement.marker.value)? @syntax.requirement.marker) @syntax.requirement.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.requirement.name", {}).get("text", ""),
                    "version": {
                        "operator": node["captures"].get("syntax.requirement.version.operator", {}).get("text", ""),
                        "number": node["captures"].get("syntax.requirement.version.number", {}).get("text", "")
                    } if "syntax.requirement.version" in node["captures"] else None,
                    "has_extras": "syntax.requirement.extras" in node["captures"],
                    "has_marker": "syntax.requirement.marker" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "file": QueryPattern(
                pattern="""
                [
                    (file
                        [(requirement) (global_opt) (comment) (path) (url)]* @structure.file.content) @structure.file.def,
                    
                    (global_opt
                        option: (option) @structure.option.name
                        [(argument) (quoted_string) (path) (url)]* @structure.option.value) @structure.option.def
                ]
                """,
                extract=lambda node: {
                    "type": "file",
                    "has_content": "structure.file.content" in node["captures"],
                    "has_options": "structure.option.def" in node["captures"]
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
                    (linebreak
                        comment: (comment) @documentation.comment.inline) @documentation.comment.line
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.comment.inline", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_inline": "documentation.comment.inline" in node["captures"]
                }
            )
        }
    },

    PatternCategory.DEPENDENCIES: {
        PatternPurpose.UNDERSTANDING: {
            "dependency": QueryPattern(
                pattern="""
                [
                    (requirement
                        package: (package) @dep.name
                        version_spec: (version_spec)? @dep.version
                        extras: (extras)? @dep.extras) @dep.def,
                    (requirement
                        url_spec: (url_spec) @dep.url) @dep.url_req,
                    (requirement
                        path_spec: (path_spec) @dep.path) @dep.path_req
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("dep.name", {}).get("text", ""),
                    "type": (
                        "versioned" if "dep.version" in node["captures"] else
                        "url" if "dep.url_req" in node["captures"] else
                        "path" if "dep.path_req" in node["captures"] else
                        "unknown"
                    ),
                    "has_extras": "dep.extras" in node["captures"]
                }
            )
        }
    },

    "REPOSITORY_LEARNING": REQUIREMENTS_PATTERNS_FOR_LEARNING
}