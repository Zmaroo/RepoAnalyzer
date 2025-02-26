"""
Query patterns for R files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

R_PATTERNS_FOR_LEARNING = {
    "data_manipulation": {
        "pattern": """
        [
            (call
                function: (identifier) @data.func {
                    match: "^(dplyr|tibble|readr|data\\.table|ggplot2|tidyr).*"
                }
                arguments: (arguments)? @data.args) @data.call,
                
            (binary_operator
                operator: ["%>%" "|>"] @data.pipe.op
                lhs: (_) @data.pipe.lhs
                rhs: (_) @data.pipe.rhs) @data.pipe,
                
            (binary_operator
                operator: "~" @data.formula.op
                lhs: (_) @data.formula.lhs
                rhs: (_) @data.formula.rhs) @data.formula,
                
            (call
                function: (identifier) @data.subset.func {
                    match: "^(subset|filter|select|slice)$"
                }
                arguments: (arguments)? @data.subset.args) @data.subset
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "data_manipulation",
            "is_data_function": "data.call" in node["captures"],
            "is_pipe": "data.pipe" in node["captures"],
            "is_formula": "data.formula" in node["captures"],
            "is_subset": "data.subset" in node["captures"],
            "function_name": node["captures"].get("data.func", {}).get("text", "") or node["captures"].get("data.subset.func", {}).get("text", ""),
            "pipe_operator": node["captures"].get("data.pipe.op", {}).get("text", ""),
            "data_pattern": (
                "tidyverse" if "data.func" in node["captures"] and 
                    any(pkg in (node["captures"].get("data.func", {}).get("text", "") or "") 
                        for pkg in ["dplyr", "tibble", "readr", "tidyr", "ggplot2"]) else
                "data.table" if "data.func" in node["captures"] and "data.table" in (node["captures"].get("data.func", {}).get("text", "") or "") else
                "pipe_chain" if "data.pipe" in node["captures"] else
                "formula" if "data.formula" in node["captures"] else
                "base_r_subset" if "data.subset" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "statistical_analysis": {
        "pattern": """
        [
            (call
                function: (identifier) @stats.func {
                    match: "^(lm|glm|t\\.test|aov|cor|wilcox\\.test|chisq\\.test|anova|kmeans|prcomp|summary|mean|median|var|sd)$"
                }
                arguments: (arguments)? @stats.args) @stats.call,
                
            (call
                function: (namespace_operator
                    lhs: (identifier) @stats.ns {
                        match: "^(stats|MASS|nlme|lme4|mgcv|survival|cluster)$"
                    }
                    rhs: (identifier) @stats.ns.func)
                arguments: (arguments)? @stats.ns.args) @stats.ns.call
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "statistical_analysis",
            "is_stats_call": "stats.call" in node["captures"],
            "is_stats_package_call": "stats.ns.call" in node["captures"],
            "function_name": node["captures"].get("stats.func", {}).get("text", "") or node["captures"].get("stats.ns.func", {}).get("text", ""),
            "package_name": node["captures"].get("stats.ns", {}).get("text", ""),
            "stats_type": (
                "regression" if any(func in (node["captures"].get("stats.func", {}).get("text", "") or node["captures"].get("stats.ns.func", {}).get("text", "") or "")
                                 for func in ["lm", "glm", "aov", "nlme", "lme4", "mgcv"]) else
                "test" if any(func in (node["captures"].get("stats.func", {}).get("text", "") or node["captures"].get("stats.ns.func", {}).get("text", "") or "")
                            for func in ["t.test", "wilcox.test", "chisq.test", "anova"]) else
                "multivariate" if any(func in (node["captures"].get("stats.func", {}).get("text", "") or node["captures"].get("stats.ns.func", {}).get("text", "") or "")
                                  for func in ["kmeans", "prcomp", "cluster"]) else
                "descriptive" if any(func in (node["captures"].get("stats.func", {}).get("text", "") or node["captures"].get("stats.ns.func", {}).get("text", "") or "")
                                  for func in ["summary", "mean", "median", "var", "sd"]) else
                "unknown"
            )
        }
    },
    
    "visualization": {
        "pattern": """
        [
            (call
                function: (identifier) @viz.base {
                    match: "^(plot|barplot|hist|boxplot|pairs|image)$"
                }
                arguments: (arguments)? @viz.base.args) @viz.base.call,
                
            (call
                function: (namespace_operator
                    lhs: (identifier) @viz.pkg {
                        match: "^(ggplot2|lattice|plotly|grid)$"
                    }
                    rhs: (identifier) @viz.pkg.func)
                arguments: (arguments)? @viz.pkg.args) @viz.pkg.call,
                
            (call
                function: (identifier) @viz.gg {
                    match: "^(ggplot|geom_\\w+|scale_\\w+|theme|facet_\\w+|coord_\\w+|aes)$"
                }
                arguments: (arguments)? @viz.gg.args) @viz.gg.call,
                
            (binary_operator
                operator: "+" @viz.gg.add.op
                lhs: (_) @viz.gg.add.lhs
                rhs: (_) @viz.gg.add.rhs) @viz.gg.add
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "visualization",
            "is_base_plot": "viz.base.call" in node["captures"],
            "is_package_plot": "viz.pkg.call" in node["captures"],
            "is_ggplot_call": "viz.gg.call" in node["captures"],
            "is_ggplot_add": "viz.gg.add" in node["captures"],
            "plot_function": node["captures"].get("viz.base", {}).get("text", "") or node["captures"].get("viz.pkg.func", {}).get("text", "") or node["captures"].get("viz.gg", {}).get("text", ""),
            "package_name": node["captures"].get("viz.pkg", {}).get("text", ""),
            "plot_type": (
                "base_graphics" if "viz.base.call" in node["captures"] else
                "lattice" if "viz.pkg.call" in node["captures"] and "lattice" == node["captures"].get("viz.pkg", {}).get("text", "") else
                "ggplot2" if (
                    "viz.gg.call" in node["captures"] or 
                    "viz.gg.add" in node["captures"] or 
                    ("viz.pkg.call" in node["captures"] and "ggplot2" == node["captures"].get("viz.pkg", {}).get("text", ""))
                ) else
                "other_package" if "viz.pkg.call" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "functional_programming": {
        "pattern": """
        [
            (call
                function: (identifier) @func.apply {
                    match: "^(apply|lapply|sapply|vapply|mapply|tapply|replicate|Map|Reduce)$"
                }
                arguments: (arguments)? @func.apply.args) @func.apply.call,
                
            (function_definition
                parameters: (formal_parameters)? @func.def.params
                body: (_) @func.def.body) @func.def,
                
            (binary_operator
                operator: ["<<-" "<-" "="] @func.anon.op
                lhs: (identifier) @func.anon.name
                rhs: (function_definition
                    parameters: (formal_parameters)? @func.anon.params
                    body: (_) @func.anon.body)) @func.anon
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "functional_programming",
            "is_apply_family": "func.apply.call" in node["captures"],
            "is_function_definition": "func.def" in node["captures"],
            "is_anonymous_function": "func.anon" in node["captures"],
            "apply_function": node["captures"].get("func.apply", {}).get("text", ""),
            "function_name": node["captures"].get("func.anon.name", {}).get("text", ""),
            "param_count": len((
                node["captures"].get("func.def.params", {}).get("text", "") or 
                node["captures"].get("func.anon.params", {}).get("text", "") or ""
            ).split(",")) if (
                node["captures"].get("func.def.params", {}).get("text", "") or 
                node["captures"].get("func.anon.params", {}).get("text", "")
            ) else 0,
            "functional_style": (
                "apply_family" if "func.apply.call" in node["captures"] else
                "named_function" if "func.def" in node["captures"] else
                "anonymous_function" if "func.anon" in node["captures"] else
                "unknown"
            )
        }
    }
}

R_PATTERNS = {
    **COMMON_PATTERNS,
    "syntax": {
        "function": {
            "pattern": """
            [
                (function_definition
                    name: (identifier) @syntax.function.name
                    parameters: (formal_parameters
                        (parameter
                            name: (identifier) @syntax.function.param.name
                            default: (_)? @syntax.function.param.default)*)? @syntax.function.params
                    body: (_) @syntax.function.body) @syntax.function.def
            ]
            """
        },
        "control": {
            "pattern": """
            [
                (if_statement
                    condition: (_) @syntax.control.if.condition
                    consequence: (_) @syntax.control.if.consequence
                    alternative: (_)? @syntax.control.if.alternative) @syntax.control.if,
                
                (for_statement
                    sequence: (_) @syntax.control.for.sequence
                    body: (_) @syntax.control.for.body) @syntax.control.for,
                
                (while_statement
                    condition: (_) @syntax.control.while.condition
                    body: (_) @syntax.control.while.body) @syntax.control.while,
                
                (repeat_statement
                    body: (_) @syntax.control.repeat.body) @syntax.control.repeat
            ]
            """
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            [
                (namespace_operator
                    lhs: (identifier) @structure.namespace.package
                    operator: "::" @structure.namespace.operator
                    rhs: (identifier) @structure.namespace.symbol) @structure.namespace.def,
                
                (library_call
                    package: (identifier) @structure.namespace.package) @structure.namespace.import
            ]
            """
        },
        "import": [
            """
            (library_call
                package: (identifier) @package) @import
            """,
            """
            (require_call
                package: (string_literal) @package) @import
            """
        ]
    },
    "semantics": {
        "variable": {
            "pattern": """
            [
                (binary_operator
                    operator: ["<-" "=" "<<-"] @semantics.variable.operator
                    lhs: (identifier) @semantics.variable.name
                    rhs: (_) @semantics.variable.value) @semantics.variable.def,
                
                (binary_operator
                    operator: ["->" "->>" "="] @semantics.variable.operator
                    lhs: (_) @semantics.variable.value
                    rhs: (identifier) @semantics.variable.name) @semantics.variable.def
            ]
            """
        },
        "call": {
            "pattern": """
            (call
                function: [(identifier) (namespace_operator)] @semantics.call.function
                arguments: (arguments)? @semantics.call.args) @semantics.call.def
            """
        }
    },
    "documentation": {
        "comment": {
            "pattern": """
            [
                (comment) @documentation.comment,
                (roxygen_comment) @documentation.docstring
            ]
            """
        }
    },
    "REPOSITORY_LEARNING": R_PATTERNS_FOR_LEARNING
} 