"""Tree-sitter patterns for Clojure programming language."""

CLOJURE_PATTERNS = {
    # Syntax patterns
    "function": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^(defn|defn-|fn)$")
            .
            (sym_lit) @name
            .
            (vec_lit)? @params
            .
            (_)* @body) @function
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^defmacro$")
            .
            (sym_lit) @name
            .
            (vec_lit)? @params
            .
            (_)* @body) @function
        """
    ],
    
    "class": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^defrecord$")
            .
            (sym_lit) @name
            .
            (vec_lit) @fields
            .
            (_)* @protocols) @class
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^defprotocol$")
            .
            (sym_lit) @name
            .
            (_)* @methods) @class
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^deftype$")
            .
            (sym_lit) @name
            .
            (vec_lit) @fields
            .
            (_)* @implementations) @class
        """
    ],
    
    # Structure patterns
    "namespace": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^ns$")
            .
            (sym_lit) @name
            .
            (_)* @body) @namespace
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^in-ns$")
            .
            (quote) @name) @namespace
        """
    ],
    
    "import": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^(:require|:use)$")
            .
            (_)+ @imports) @import
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^import$")
            .
            (_)+ @imports) @import
        """
    ],
    
    # Semantics patterns
    "variable": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^def$")
            .
            (sym_lit) @name
            .
            (_)? @value) @variable
        """,
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^defonce$")
            .
            (sym_lit) @name
            .
            (_)? @value) @variable
        """
    ],
    
    "expression": [
        """
        (list_lit
            .
            (sym_lit) @operator
            (#match? @operator "^(->|->>|as->|cond->|cond->>|some->|some->>)$")
            .
            (_)+ @forms) @expression
        """,
        """
        (list_lit
            .
            (sym_lit) @operator
            (#match? @operator "^(if|when|cond|case|condp)$")
            .
            (_)+ @branches) @expression
        """
    ],
    
    # Documentation patterns
    "docstring": [
        """
        (list_lit
            .
            (sym_lit) @def_type
            (#match? @def_type "^(defn|defmacro|defprotocol|defrecord|deftype)$")
            .
            (sym_lit)
            .
            (str_lit) @content) @docstring
        """
    ],
    
    "comment": [
        """
        (comment) @comment
        """,
        """
        (dis_expr) @comment
        """
    ]
}

# Additional metadata for pattern categories
PATTERN_METADATA = {
    "syntax": {
        "function": {
            "contains": ["params", "body", "docstring"],
            "contained_by": ["namespace"]
        },
        "class": {
            "contains": ["fields", "methods", "protocols", "implementations", "docstring"],
            "contained_by": ["namespace"]
        }
    },
    "structure": {
        "namespace": {
            "contains": ["import", "function", "class", "variable"],
            "contained_by": []
        },
        "import": {
            "contains": [],
            "contained_by": ["namespace"]
        }
    },
    "semantics": {
        "variable": {
            "contains": ["value"],
            "contained_by": ["namespace", "function"]
        },
        "expression": {
            "contains": ["forms", "branches"],
            "contained_by": ["function", "variable"]
        }
    },
    "documentation": {
        "docstring": {
            "contains": [],
            "contained_by": ["function", "class", "namespace"]
        },
        "comment": {
            "contains": [],
            "contained_by": ["function", "class", "namespace", "expression"]
        }
    }
} 