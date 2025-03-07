"""
Query patterns for R files.
"""

from parsers.types import (
    FileType, PatternCategory, PatternPurpose,
    QueryPattern, PatternDefinition
)
from .common import COMMON_PATTERNS

R_PATTERNS = {
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (formal_parameters
                            (parameter
                                name: (identifier) @syntax.function.param.name
                                default: (_)? @syntax.function.param.default)*)? @syntax.function.params
                        body: (_) @syntax.function.body) @syntax.function.def
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "type": "function",
                    "has_params": "syntax.function.params" in node["captures"],
                    "param_names": [
                        param["text"] for param in node["captures"].get("syntax.function.param.name", [])
                    ] if "syntax.function.param.name" in node["captures"] else []
                }
            ),
            "control": QueryPattern(
                pattern="""
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
                """,
                extract=lambda node: {
                    "type": (
                        "if" if "syntax.control.if" in node["captures"] else
                        "for" if "syntax.control.for" in node["captures"] else
                        "while" if "syntax.control.while" in node["captures"] else
                        "repeat" if "syntax.control.repeat" in node["captures"] else
                        "other"
                    ),
                    "has_condition": any(
                        key in node["captures"] for key in 
                        ["syntax.control.if.condition", "syntax.control.while.condition"]
                    ),
                    "has_alternative": "syntax.control.if.alternative" in node["captures"]
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
                    (roxygen_comment) @documentation.docstring
                ]
                """,
                extract=lambda node: {
                    "text": (
                        node["captures"].get("documentation.comment", {}).get("text", "") or
                        node["captures"].get("documentation.docstring", {}).get("text", "")
                    ),
                    "type": "comment",
                    "is_roxygen": "documentation.docstring" in node["captures"]
                }
            )
        }
    },

    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "namespace": QueryPattern(
                pattern="""
                [
                    (namespace_operator
                        lhs: (identifier) @structure.namespace.package
                        operator: "::" @structure.namespace.operator
                        rhs: (identifier) @structure.namespace.symbol) @structure.namespace.def,
                    (library_call
                        package: (identifier) @structure.namespace.package) @structure.namespace.import
                ]
                """,
                extract=lambda node: {
                    "type": "namespace",
                    "package": node["captures"].get("structure.namespace.package", {}).get("text", ""),
                    "is_import": "structure.namespace.import" in node["captures"],
                    "symbol": node["captures"].get("structure.namespace.symbol", {}).get("text", "") if "structure.namespace.def" in node["captures"] else None
                }
            )
        }
    },

    PatternCategory.LEARNING: {
        PatternPurpose.DATA_MANIPULATION: {
            "data_manipulation": QueryPattern(
                pattern="""
                [
                    (call
                        function: (identifier) @learning.data.func {
                            match: "^(dplyr|tibble|readr|data\\.table|ggplot2|tidyr).*"
                        }
                        arguments: (arguments)? @learning.data.args) @learning.data.call,
                    (binary_operator
                        operator: ["%>%" "|>"] @learning.data.pipe.op
                        lhs: (_) @learning.data.pipe.lhs
                        rhs: (_) @learning.data.pipe.rhs) @learning.data.pipe,
                    (binary_operator
                        operator: "~" @learning.data.formula.op
                        lhs: (_) @learning.data.formula.lhs
                        rhs: (_) @learning.data.formula.rhs) @learning.data.formula,
                    (call
                        function: (identifier) @learning.data.subset.func {
                            match: "^(subset|filter|select|slice)$"
                        }
                        arguments: (arguments)? @learning.data.subset.args) @learning.data.subset
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "data_manipulation",
                    "is_data_function": "learning.data.call" in node["captures"],
                    "is_pipe": "learning.data.pipe" in node["captures"],
                    "is_formula": "learning.data.formula" in node["captures"],
                    "is_subset": "learning.data.subset" in node["captures"],
                    "function_name": node["captures"].get("learning.data.func", {}).get("text", "") or node["captures"].get("learning.data.subset.func", {}).get("text", ""),
                    "pipe_operator": node["captures"].get("learning.data.pipe.op", {}).get("text", ""),
                    "data_pattern": (
                        "tidyverse" if "learning.data.func" in node["captures"] and 
                            any(pkg in (node["captures"].get("learning.data.func", {}).get("text", "") or "") 
                                for pkg in ["dplyr", "tibble", "readr", "tidyr", "ggplot2"]) else
                        "data.table" if "learning.data.func" in node["captures"] and "data.table" in (node["captures"].get("learning.data.func", {}).get("text", "") or "") else
                        "pipe_chain" if "learning.data.pipe" in node["captures"] else
                        "formula" if "learning.data.formula" in node["captures"] else
                        "base_r_subset" if "learning.data.subset" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.STATISTICAL_ANALYSIS: {
            "statistical_analysis": QueryPattern(
                pattern="""
                [
                    (call
                        function: (identifier) @learning.stats.func {
                            match: "^(lm|glm|t\\.test|aov|cor|wilcox\\.test|chisq\\.test|anova|kmeans|prcomp|summary|mean|median|var|sd)$"
                        }
                        arguments: (arguments)? @learning.stats.args) @learning.stats.call,
                    (call
                        function: (namespace_operator
                            lhs: (identifier) @learning.stats.ns {
                                match: "^(stats|MASS|nlme|lme4|mgcv|survival|cluster)$"
                            }
                            rhs: (identifier) @learning.stats.ns.func)
                        arguments: (arguments)? @learning.stats.ns.args) @learning.stats.ns.call
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "statistical_analysis",
                    "is_stats_call": "learning.stats.call" in node["captures"],
                    "is_stats_package_call": "learning.stats.ns.call" in node["captures"],
                    "function_name": node["captures"].get("learning.stats.func", {}).get("text", "") or node["captures"].get("learning.stats.ns.func", {}).get("text", ""),
                    "package_name": node["captures"].get("learning.stats.ns", {}).get("text", ""),
                    "stats_type": (
                        "regression" if any(func in (node["captures"].get("learning.stats.func", {}).get("text", "") or node["captures"].get("learning.stats.ns.func", {}).get("text", "") or "")
                                     for func in ["lm", "glm", "aov", "nlme", "lme4", "mgcv"]) else
                        "test" if any(func in (node["captures"].get("learning.stats.func", {}).get("text", "") or node["captures"].get("learning.stats.ns.func", {}).get("text", "") or "")
                                for func in ["t.test", "wilcox.test", "chisq.test", "anova"]) else
                        "multivariate" if any(func in (node["captures"].get("learning.stats.func", {}).get("text", "") or node["captures"].get("learning.stats.ns.func", {}).get("text", "") or "")
                                      for func in ["kmeans", "prcomp", "cluster"]) else
                        "descriptive" if any(func in (node["captures"].get("learning.stats.func", {}).get("text", "") or node["captures"].get("learning.stats.ns.func", {}).get("text", "") or "")
                                      for func in ["summary", "mean", "median", "var", "sd"]) else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.VISUALIZATION: {
            "visualization": QueryPattern(
                pattern="""
                [
                    (call
                        function: (identifier) @learning.viz.base {
                            match: "^(plot|barplot|hist|boxplot|pairs|image)$"
                        }
                        arguments: (arguments)? @learning.viz.base.args) @learning.viz.base.call,
                    (call
                        function: (namespace_operator
                            lhs: (identifier) @learning.viz.pkg {
                                match: "^(ggplot2|lattice|plotly|grid)$"
                            }
                            rhs: (identifier) @learning.viz.pkg.func)
                        arguments: (arguments)? @learning.viz.pkg.args) @learning.viz.pkg.call,
                    (call
                        function: (identifier) @learning.viz.gg {
                            match: "^(ggplot|geom_\\w+|scale_\\w+|theme|facet_\\w+|coord_\\w+|aes)$"
                        }
                        arguments: (arguments)? @learning.viz.gg.args) @learning.viz.gg.call,
                    (binary_operator
                        operator: "+" @learning.viz.gg.add.op
                        lhs: (_) @learning.viz.gg.add.lhs
                        rhs: (_) @learning.viz.gg.add.rhs) @learning.viz.gg.add
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "visualization",
                    "is_base_plot": "learning.viz.base.call" in node["captures"],
                    "is_package_plot": "learning.viz.pkg.call" in node["captures"],
                    "is_ggplot_call": "learning.viz.gg.call" in node["captures"],
                    "is_ggplot_add": "learning.viz.gg.add" in node["captures"],
                    "plot_function": node["captures"].get("learning.viz.base", {}).get("text", "") or node["captures"].get("learning.viz.pkg.func", {}).get("text", "") or node["captures"].get("learning.viz.gg", {}).get("text", ""),
                    "package_name": node["captures"].get("learning.viz.pkg", {}).get("text", ""),
                    "plot_type": (
                        "base_graphics" if "learning.viz.base.call" in node["captures"] else
                        "lattice" if "learning.viz.pkg.call" in node["captures"] and "lattice" == node["captures"].get("learning.viz.pkg", {}).get("text", "") else
                        "ggplot2" if (
                            "learning.viz.gg.call" in node["captures"] or 
                            "learning.viz.gg.add" in node["captures"] or 
                            ("learning.viz.pkg.call" in node["captures"] and "ggplot2" == node["captures"].get("learning.viz.pkg", {}).get("text", ""))
                        ) else
                        "other_package" if "learning.viz.pkg.call" in node["captures"] else
                        "unknown"
                    )
                }
            )
        },
        PatternPurpose.FUNCTIONAL: {
            "functional_programming": QueryPattern(
                pattern="""
                [
                    (call
                        function: (identifier) @learning.func.apply {
                            match: "^(apply|lapply|sapply|vapply|mapply|tapply|replicate|Map|Reduce)$"
                        }
                        arguments: (arguments)? @learning.func.apply.args) @learning.func.apply.call,
                    (function_definition
                        parameters: (formal_parameters)? @learning.func.def.params
                        body: (_) @learning.func.def.body) @learning.func.def,
                    (binary_operator
                        operator: ["<<-" "<-" "="] @learning.func.anon.op
                        lhs: (identifier) @learning.func.anon.name
                        rhs: (function_definition
                            parameters: (formal_parameters)? @learning.func.anon.params
                            body: (_) @learning.func.anon.body)) @learning.func.anon
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "functional_programming",
                    "is_apply_family": "learning.func.apply.call" in node["captures"],
                    "is_function_definition": "learning.func.def" in node["captures"],
                    "is_anonymous_function": "learning.func.anon" in node["captures"],
                    "apply_function": node["captures"].get("learning.func.apply", {}).get("text", ""),
                    "function_name": node["captures"].get("learning.func.anon.name", {}).get("text", ""),
                    "param_count": len((
                        node["captures"].get("learning.func.def.params", {}).get("text", "") or 
                        node["captures"].get("learning.func.anon.params", {}).get("text", "") or ""
                    ).split(",")) if (
                        node["captures"].get("learning.func.def.params", {}).get("text", "") or 
                        node["captures"].get("learning.func.anon.params", {}).get("text", "")
                    ) else 0,
                    "functional_style": (
                        "apply_family" if "learning.func.apply.call" in node["captures"] else
                        "named_function" if "learning.func.def" in node["captures"] else
                        "anonymous_function" if "learning.func.anon" in node["captures"] else
                        "unknown"
                    )
                }
            )
        }
    }
}

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
    "REPOSITORY_LEARNING": R_PATTERNS_FOR_LEARNING
} 