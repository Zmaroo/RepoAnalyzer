"""Python-specific Tree-sitter patterns."""

from parsers.types import FileType
from .common import COMMON_PATTERNS
from parsers.types import (
    FileType, PatternCategory, PatternPurpose, 
    QueryPattern, PatternDefinition
)

PYTHON_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    PatternCategory.SYNTAX: {
        PatternPurpose.UNDERSTANDING: {
            "function": QueryPattern(
                pattern="""
                [
                    (function_definition
                        name: (identifier) @syntax.function.name
                        parameters: (parameters
                            [(identifier) @syntax.function.param.name
                             (typed_parameter
                                name: (identifier) @syntax.function.param.name
                                type: (type) @syntax.function.param.type)
                             (default_parameter
                                name: (identifier) @syntax.function.param.name
                                value: (_) @syntax.function.param.default)
                             (list_splat_pattern
                                name: (identifier) @syntax.function.param.args)
                             (dictionary_splat_pattern
                                name: (identifier) @syntax.function.param.kwargs)]* @syntax.function.params)
                        return_type: (type)? @syntax.function.return_type
                        body: (block) @syntax.function.body) @syntax.function.def,
                    
                    (class_definition
                        body: (block
                            (function_definition
                                decorators: (decorator
                                    name: [(identifier) (attribute)]
                                    (#match? @name "^(classmethod|staticmethod|property)$"))? @syntax.function.method.decorator
                                name: (identifier) @syntax.function.method.name
                                parameters: (parameters) @syntax.function.method.params
                                body: (block) @syntax.function.method.body) @syntax.function.method))
                ]
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.function.name", {}).get("text", ""),
                    "params": [p.text.decode('utf8') for p in node["captures"].get("syntax.function.param.name", [])],
                    "decorators": [d.text.decode('utf8') for d in node["captures"].get("syntax.function.decorator.name", [])]
                },
                description="Matches Python function and method definitions",
                examples=[
                    "def my_function(x: int, y: str = 'default') -> None: pass",
                    "@property\ndef value(self): return self._value"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            ),
            
            "class": QueryPattern(
                pattern="""
                (class_definition
                    decorators: (decorator)* @syntax.class.decorators
                    name: (identifier) @syntax.class.name
                    type_parameters: (type_parameter)? @syntax.class.type_params
                    superclasses: (argument_list
                        [(identifier) @syntax.class.base
                         (keyword_argument
                            name: (identifier) @syntax.class.metaclass.name
                            value: (_) @syntax.class.metaclass.value)]*)? @syntax.class.bases
                    body: (block) @syntax.class.body) @syntax.class.def
                """,
                extract=lambda node: {
                    "name": node["captures"].get("syntax.class.name", {}).get("text", ""),
                    "bases": [b.text.decode('utf8') for b in node["captures"].get("syntax.class.base", [])]
                },
                description="Matches Python class definitions",
                examples=[
                    "class MyClass(BaseClass): pass",
                    "@dataclass\nclass Point: x: int; y: int"
                ],
                category=PatternCategory.SYNTAX,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.SEMANTICS: {
        PatternPurpose.UNDERSTANDING: {
            "type": QueryPattern(
                pattern="""
                [
                    (type_parameter
                        name: (identifier) @semantics.type.param.name
                        bound: (type)? @semantics.type.param.bound) @semantics.type.param,
                    
                    (union_type
                        types: (type)+ @semantics.type.union.member) @semantics.type.union,
                    
                    (generic_type
                        name: (identifier) @semantics.type.generic.name
                        type_arguments: (type_parameter_list)? @semantics.type.generic.args) @semantics.type.generic
                ]
                """,
                extract=lambda node: {
                    "type": node["captures"].get("semantics.type.annotation", {}).get("text", ""),
                    "kind": ("type_param" if "semantics.type.param" in node["captures"] else
                            "union" if "semantics.type.union" in node["captures"] else
                            "generic" if "semantics.type.generic" in node["captures"] else
                            "annotation")
                },
                description="Matches Python type annotations",
                examples=[
                    "T = TypeVar('T', bound=Number)",
                    "Union[str, int]",
                    "List[T]"
                ],
                category=PatternCategory.SEMANTICS,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.DOCUMENTATION: {
        PatternPurpose.UNDERSTANDING: {
            "docstring": QueryPattern(
                pattern="""
                [
                    (module
                        (expression_statement
                            (string) @documentation.module.docstring)) @documentation.module,
                    
                    (function_definition
                        body: (block
                            (expression_statement
                                (string) @documentation.function.docstring))) @documentation.function,
                    
                    (class_definition
                        body: (block
                            (expression_statement
                                (string) @documentation.class.docstring))) @documentation.class,
                    
                    (comment) @documentation.comment
                ]
                """,
                extract=lambda node: {
                    "text": node["captures"].get("documentation.module.docstring", {}).get("text", "") or
                           node["captures"].get("documentation.function.docstring", {}).get("text", "") or
                           node["captures"].get("documentation.class.docstring", {}).get("text", "") or
                           node["captures"].get("documentation.comment", {}).get("text", "")
                },
                description="Matches Python docstrings and comments",
                examples=[
                    '"""Module docstring."""',
                    '"""Function docstring with parameters.\n\nArgs:\n    x: Parameter\n"""',
                    "# Line comment"
                ],
                category=PatternCategory.DOCUMENTATION,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    },
    
    PatternCategory.STRUCTURE: {
        PatternPurpose.UNDERSTANDING: {
            "import_export": QueryPattern(
                pattern="""
                [
                    (import_statement
                        name: (dotted_name) @structure.import.module) @structure.import,
                    
                    (import_from_statement
                        module_name: (dotted_name)? @structure.import.from.module
                        name: [(dotted_name) (wildcard_import)] @structure.import.from.name) @structure.import.from
                ]
                """,
                extract=lambda node: {
                    "module": node["captures"].get("structure.import.module", {}).get("text", "") or
                             node["captures"].get("structure.import.from.module", {}).get("text", ""),
                    "name": node["captures"].get("structure.import.name", {}).get("text", "") or
                            node["captures"].get("structure.import.from.name", {}).get("text", "")
                },
                description="Matches Python import statements",
                examples=[
                    "import os.path",
                    "from typing import List, Optional"
                ],
                category=PatternCategory.STRUCTURE,
                purpose=PatternPurpose.UNDERSTANDING
            )
        }
    }
}

# Repository learning patterns for Python
PYTHON_PATTERNS_FOR_LEARNING = {
    PatternCategory.LEARNING: {
        PatternPurpose.LEARNING: {
            "modern_python_features": QueryPattern(
                pattern="""
                [
                    (assignment
                        left: [(tuple_pattern) (list_pattern)] @modern.unpack.left
                        right: (_) @modern.unpack.right) @modern.unpack,
                        
                    (function_definition
                        parameters: (parameters
                            (typed_parameter
                                name: (identifier) @modern.typing.param.name
                                type: (type) @modern.typing.param.type)) @modern.typing.params
                        return_type: (type) @modern.typing.return) @modern.typing.func,
                        
                    (class_definition
                        superclasses: (argument_list
                            (identifier) @modern.protocol.name
                            (#match? @modern.protocol.name "Protocol|ABC")) @modern.protocol.base) @modern.protocol.class,
                            
                    (function_definition
                        decorators: (decorator
                            name: (identifier) @modern.decorator.name
                            (#match? @modern.decorator.name "^(cached_property|dataclass|staticmethod|classmethod|property)$")) @modern.decorator) @modern.decorated.func,
                            
                    (class_definition
                        decorators: (decorator
                            name: (identifier) @modern.class.dec.name
                            (#match? @modern.class.dec.name "^(dataclass|total_ordering|enum_auto)$")) @modern.class.dec) @modern.decorated.class,
                            
                    (for_statement
                        body: (block
                            (expression_statement
                                (await_expr) @modern.async.await)) @modern.async.body) @modern.async.for,
                                
                    (function_definition
                        body: (block
                            (expression_statement
                                (yield_expr) @modern.generator.yield)) @modern.generator.body) @modern.generator.func,
                                
                    (with_statement
                        body: (block
                            (expression_statement
                                (match_statement) @modern.match.stmt))) @modern.with.match
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "modern_python_features",
                    "uses_unpacking": "modern.unpack" in node["captures"],
                    "uses_type_hints": "modern.typing.func" in node["captures"],
                    "uses_protocols": "modern.protocol.class" in node["captures"],
                    "uses_modern_decorators": "modern.decorator" in node["captures"],
                    "uses_dataclasses": "modern.class.dec" in node["captures"] and "dataclass" in (node["captures"].get("modern.class.dec.name", {}).get("text", "") or ""),
                    "uses_async": "modern.async.for" in node["captures"],
                    "uses_generators": "modern.generator.func" in node["captures"],
                    "uses_match_statement": "modern.match.stmt" in node["captures"],
                    "python_level": (
                        "modern" if any([
                            "modern.protocol.class" in node["captures"],
                            "modern.class.dec" in node["captures"],
                            "modern.match.stmt" in node["captures"],
                            "modern.typing.func" in node["captures"]
                        ]) else "intermediate" if any([
                            "modern.unpack" in node["captures"],
                            "modern.decorator" in node["captures"],
                            "modern.async.for" in node["captures"],
                            "modern.generator.func" in node["captures"]
                        ]) else "basic"
                    ),
                    "feature_name": (
                        "type_hints" if "modern.typing.func" in node["captures"] else
                        "protocols" if "modern.protocol.class" in node["captures"] else
                        "dataclasses" if "modern.class.dec" in node["captures"] and "dataclass" in (node["captures"].get("modern.class.dec.name", {}).get("text", "") or "") else
                        "match_statement" if "modern.match.stmt" in node["captures"] else
                        "async_await" if "modern.async.for" in node["captures"] else
                        "generators" if "modern.generator.func" in node["captures"] else
                        "unpacking" if "modern.unpack" in node["captures"] else
                        "decorators" if "modern.decorator" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches modern Python features",
                examples=[
                    "def func(x: int) -> str: ...",
                    "@dataclass\nclass Point: x: int; y: int",
                    "async def fetch(): await response"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "design_patterns": QueryPattern(
                pattern="""
                [
                    (class_definition
                        name: (identifier) @design.singleton.name {
                            match: ".*Singleton$"
                        }
                        body: (block
                            (function_definition
                                name: (identifier) @design.singleton.method {
                                    match: "^(__new__|getInstance|get_instance)$"
                                }))) @design.singleton,
                                
                    (class_definition
                        name: (identifier) @design.factory.name {
                            match: ".*Factory$"
                        }
                        body: (block
                            (function_definition
                                name: (identifier) @design.factory.method {
                                    match: "^(create|build|get|make).*$"
                                }))) @design.factory,
                                
                    (class_definition
                        body: (block
                            (function_definition
                                name: (identifier) @design.observer.method {
                                    match: "^(notify|update|subscribe|unsubscribe|attach|detach)$"
                                }))) @design.observer,
                                
                    (class_definition
                        body: (block
                            (function_definition
                                name: (identifier) @design.builder.method {
                                    match: "^(build|with_|add_|set_).*$"
                                }
                                body: (block
                                    (return_statement
                                        (identifier) @design.builder.return {
                                            match: "^self$"
                                        }))))) @design.builder,
                                        
                    (class_definition
                        name: (identifier) @design.decorator.name {
                            match: ".*Decorator$"
                        }
                        superclasses: (argument_list) @design.decorator.base
                        body: (block
                            (function_definition
                                name: (identifier) @design.decorator.method {
                                    match: "^(__init__|__call__)$"
                                }))) @design.decorator.class,
                                
                    (class_definition
                        name: (identifier) @design.adapter.name {
                            match: ".*Adapter$"
                        }
                        body: (block)) @design.adapter
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "design_patterns",
                    "is_singleton": "design.singleton" in node["captures"],
                    "is_factory": "design.factory" in node["captures"],
                    "is_observer": "design.observer" in node["captures"],
                    "is_builder": "design.builder" in node["captures"],
                    "is_decorator": "design.decorator.class" in node["captures"],
                    "is_adapter": "design.adapter" in node["captures"],
                    "pattern_name": (
                        "singleton" if "design.singleton" in node["captures"] else
                        "factory" if "design.factory" in node["captures"] else
                        "observer" if "design.observer" in node["captures"] else
                        "builder" if "design.builder" in node["captures"] else
                        "decorator" if "design.decorator.class" in node["captures"] else
                        "adapter" if "design.adapter" in node["captures"] else
                        "unknown"
                    ),
                    "class_name": (
                        node["captures"].get("design.singleton.name", {}).get("text", "") or
                        node["captures"].get("design.factory.name", {}).get("text", "") or
                        node["captures"].get("design.decorator.name", {}).get("text", "") or
                        node["captures"].get("design.adapter.name", {}).get("text", "")
                    ),
                    "method_name": (
                        node["captures"].get("design.singleton.method", {}).get("text", "") or
                        node["captures"].get("design.factory.method", {}).get("text", "") or
                        node["captures"].get("design.observer.method", {}).get("text", "") or
                        node["captures"].get("design.builder.method", {}).get("text", "") or
                        node["captures"].get("design.decorator.method", {}).get("text", "")
                    )
                },
                description="Matches Python design patterns",
                examples=[
                    "class MySingleton:\n    _instance = None\n    @classmethod\n    def getInstance(cls): ...",
                    "class ShapeFactory:\n    def create_circle(self): ...",
                    "class LoggerDecorator:\n    def __init__(self, wrapped): self.wrapped = wrapped"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "performance_optimization": QueryPattern(
                pattern="""
                [
                    (import_from_statement
                        module_name: (dotted_name) @perf.lib.name {
                            match: "^(numba|numpy|pandas|cython)$"
                        }) @perf.lib.import,
                        
                    (function_definition
                        decorators: (decorator
                            name: [(identifier) (attribute)] @perf.dec.name {
                                match: "^(jit|njit|vectorize|guvectorize|lru_cache|cache|cached_property)$"
                            }) @perf.dec) @perf.dec.func,
                            
                    (function_definition
                        body: (block
                            (with_statement
                                expression: (call
                                    function: (attribute
                                        attribute: (identifier) @perf.context.name {
                                            match: "^(parallel|nogil|boundscheck|wraparound)$"
                                        })) @perf.context.call) @perf.context)) @perf.context.func,
                                        
                    (call
                        function: (attribute
                            object: (identifier) @perf.numpy.obj {
                                match: "^(np|numpy)$"
                            }
                            attribute: (identifier) @perf.numpy.method)) @perf.numpy.call,
                            
                    (for_statement
                        body: (block
                            (expression_statement
                                (assignment
                                    left: (subscript
                                        value: (identifier) @perf.inplace.array)
                                    right: (_) @perf.inplace.expr)))) @perf.inplace.loop,
                                    
                    (comprehension
                        body: (_) @perf.compr.body
                        iterable: (_) @perf.compr.iter) @perf.compr
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "performance_optimization",
                    "uses_optimization_libraries": "perf.lib.import" in node["captures"],
                    "uses_jit_compilation": "perf.dec" in node["captures"] and any(
                        jit in (node["captures"].get("perf.dec.name", {}).get("text", "") or "")
                        for jit in ["jit", "njit", "vectorize", "guvectorize"]
                    ),
                    "uses_caching": "perf.dec" in node["captures"] and any(
                        cache in (node["captures"].get("perf.dec.name", {}).get("text", "") or "")
                        for cache in ["lru_cache", "cache", "cached_property"]
                    ),
                    "uses_numpy_vectorization": "perf.numpy.call" in node["captures"],
                    "uses_comprehensions": "perf.compr" in node["captures"],
                    "uses_inplace_operations": "perf.inplace.loop" in node["captures"],
                    "uses_parallel_contexts": "perf.context" in node["captures"] and "parallel" in (node["captures"].get("perf.context.name", {}).get("text", "") or ""),
                    "optimization_library": node["captures"].get("perf.lib.name", {}).get("text", ""),
                    "optimization_technique": (
                        "jit_compilation" if "perf.dec" in node["captures"] and any(
                            jit in (node["captures"].get("perf.dec.name", {}).get("text", "") or "")
                            for jit in ["jit", "njit", "vectorize", "guvectorize"]
                        ) else
                        "caching" if "perf.dec" in node["captures"] and any(
                            cache in (node["captures"].get("perf.dec.name", {}).get("text", "") or "")
                            for cache in ["lru_cache", "cache", "cached_property"]
                        ) else
                        "numpy_vectorization" if "perf.numpy.call" in node["captures"] else
                        "comprehensions" if "perf.compr" in node["captures"] else
                        "inplace_operations" if "perf.inplace.loop" in node["captures"] else
                        "parallel_contexts" if "perf.context" in node["captures"] and "parallel" in (node["captures"].get("perf.context.name", {}).get("text", "") or "") else
                        "unknown"
                    )
                },
                description="Matches Python performance optimization patterns",
                examples=[
                    "@numba.jit\ndef calculate(x): return x * 2",
                    "@lru_cache(maxsize=128)\ndef fibonacci(n): ...",
                    "with nogil: process_data()"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            ),
            
            "error_handling": QueryPattern(
                pattern="""
                [
                    (try_statement
                        body: (block) @error.try
                        except_clauses: (except_clause)+ @error.except
                        finally_clause: (finally_clause)? @error.finally) @error.try_except,
                        
                    (class_definition
                        superclasses: (argument_list
                            (identifier) @error.exc.base {
                                match: "^(Exception|ValueError|TypeError|RuntimeError).*$"
                            }) @error.exc.bases) @error.exc.class,
                            
                    (raise_statement
                        (call
                            function: (identifier) @error.raise.exc)) @error.raise,
                            
                    (function_definition
                        body: (block
                            (if_statement
                                condition: (_) @error.check.cond
                                consequence: (block
                                    (raise_statement) @error.check.raise)))) @error.check.func,
                                    
                    (with_statement
                        expression: (call
                            function: (identifier) @error.context.func {
                                match: "^(contextlib|suppress)$"
                            }) @error.context.call) @error.context,
                            
                    (assert_statement
                        condition: (_) @error.assert.cond
                        message: (_)? @error.assert.msg) @error.assert,
                        
                    (function_definition
                        body: (block
                            (expression_statement
                                (call
                                    function: (attribute
                                        object: (identifier) @error.log.obj {
                                            match: "^(logging|logger)$"
                                        }
                                        attribute: (identifier) @error.log.level {
                                            match: "^(debug|info|warning|error|critical|exception)$"
                                        })))) @error.log.func) @error.log
                ]
                """,
                extract=lambda node: {
                    "pattern_type": "error_handling",
                    "uses_try_except": "error.try_except" in node["captures"],
                    "defines_custom_exceptions": "error.exc.class" in node["captures"],
                    "uses_raise": "error.raise" in node["captures"],
                    "uses_validation_checks": "error.check.func" in node["captures"],
                    "uses_context_managers": "error.context" in node["captures"],
                    "uses_assertions": "error.assert" in node["captures"],
                    "uses_logging": "error.log" in node["captures"],
                    "has_finally_clause": "error.finally" in node["captures"],
                    "exception_type": node["captures"].get("error.exc.base", {}).get("text", "") or node["captures"].get("error.raise.exc", {}).get("text", ""),
                    "logging_level": node["captures"].get("error.log.level", {}).get("text", ""),
                    "error_handling_approach": (
                        "try_except_finally" if "error.try_except" in node["captures"] and "error.finally" in node["captures"] else
                        "try_except" if "error.try_except" in node["captures"] else
                        "custom_exceptions" if "error.exc.class" in node["captures"] else
                        "exception_raising" if "error.raise" in node["captures"] else
                        "validation_checks" if "error.check.func" in node["captures"] else
                        "context_managers" if "error.context" in node["captures"] else
                        "assertions" if "error.assert" in node["captures"] else
                        "logging" if "error.log" in node["captures"] else
                        "unknown"
                    )
                },
                description="Matches Python error handling patterns",
                examples=[
                    "try:\n    risky_operation()\nexcept ValueError as e:\n    handle_error(e)\nfinally:\n    cleanup()",
                    "class CustomError(Exception): pass",
                    "if not valid: raise ValueError('Invalid input')"
                ],
                category=PatternCategory.LEARNING,
                purpose=PatternPurpose.LEARNING
            )
        }
    }
}

# Add the repository learning patterns to the main patterns
PYTHON_PATTERNS.update(PYTHON_PATTERNS_FOR_LEARNING) 