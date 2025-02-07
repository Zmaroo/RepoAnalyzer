"""Query patterns package."""

from .ada import ADA_PATTERNS
from .bash import BASH_PATTERNS
from .c import C_PATTERNS
from .clojure import CLOJURE_PATTERNS
from .dart import DART_PATTERNS
from .elixir import ELIXIR_PATTERNS
from .erlang import ERLANG_PATTERNS
from .gdscript import GDSCRIPT_PATTERNS
from .json import JSON_PATTERNS
from .js_base import JS_BASE_PATTERNS
from .javascript import JAVASCRIPT_PATTERNS
from .typescript import TYPESCRIPT_PATTERNS
from .tsx import TSX_PATTERNS
from .julia import JULIA_PATTERNS
from .r import R_PATTERNS
from .cpp import CPP_PATTERNS
from .csharp import CSHARP_PATTERNS
from .go import GO_PATTERNS
from .groovy import GROOVY_PATTERNS
from .haskell import HASKELL_PATTERNS
from .java import JAVA_PATTERNS
from .kotlin import KOTLIN_PATTERNS
from .lua import LUA_PATTERNS
from .markup import (
    HTML_PATTERNS,
    YAML_PATTERNS,
    TOML_PATTERNS,
    DOCKERFILE_PATTERNS,
    MARKDOWN_PATTERNS,
    REQUIREMENTS_PATTERNS,
    GITIGNORE_PATTERNS,
    MAKEFILE_PATTERNS,
)
from .objectivec import OBJECTIVEC_PATTERNS
from .perl import PERL_PATTERNS
from .php import PHP_PATTERNS
from .powershell import POWERSHELL_PATTERNS
from .python import PYTHON_PATTERNS
from .commonlisp import COMMONLISP_PATTERNS
from .racket import RACKET_PATTERNS
from .ruby import RUBY_PATTERNS
from .rust import RUST_PATTERNS
from .scala import SCALA_PATTERNS
from .sql import SQL_PATTERNS
from .squirrel import SQUIRREL_PATTERNS
from .swift import SWIFT_PATTERNS
from .vue import VUE_PATTERNS
from .svelte import SVELTE_PATTERNS
from .zig import ZIG_PATTERNS
from .matlab import MATLAB_PATTERNS
from .nim import NIM_PATTERNS
from .cuda import CUDA_PATTERNS
from .hcl import HCL_PATTERNS
from .proto import PROTO_PATTERNS
from .graphql import GRAPHQL_PATTERNS
from .dockerfil import DOCKERFILE_PATTERNS
from .cmake import CMAKE_PATTERNS
from .toml import TOML_PATTERNS
from .xml import XML_PATTERNS

# Export all patterns in a dictionary
query_patterns = {
    'ada': ADA_PATTERNS,
    'bash': BASH_PATTERNS,
    'c': C_PATTERNS,
    'clojure': CLOJURE_PATTERNS,
    'dart': DART_PATTERNS,
    'elixir': ELIXIR_PATTERNS,
    'erlang': ERLANG_PATTERNS,
    'gdscript': GDSCRIPT_PATTERNS,
    'json': JSON_PATTERNS,
    'javascript': JAVASCRIPT_PATTERNS,
    'typescript': TYPESCRIPT_PATTERNS,
    'tsx': TSX_PATTERNS,
    'julia': JULIA_PATTERNS,
    'r': R_PATTERNS,
    'cpp': CPP_PATTERNS,
    'csharp': CSHARP_PATTERNS,
    'go': GO_PATTERNS,
    'groovy': GROOVY_PATTERNS,
    'haskell': HASKELL_PATTERNS,
    'java': JAVA_PATTERNS,
    'kotlin': KOTLIN_PATTERNS,
    'lua': LUA_PATTERNS,
    'markup': {
        'html': HTML_PATTERNS,
        'yaml': YAML_PATTERNS,
        'toml': TOML_PATTERNS,
        'dockerfile': DOCKERFILE_PATTERNS,
        'markdown': MARKDOWN_PATTERNS,
        'requirements': REQUIREMENTS_PATTERNS,
        'gitignore': GITIGNORE_PATTERNS,
        'makefile': MAKEFILE_PATTERNS
    },
    'objectivec': OBJECTIVEC_PATTERNS,
    'perl': PERL_PATTERNS,
    'php': PHP_PATTERNS,
    'powershell': POWERSHELL_PATTERNS,
    'python': PYTHON_PATTERNS,
    'commonlisp': COMMONLISP_PATTERNS,
    'racket': RACKET_PATTERNS,
    'ruby': RUBY_PATTERNS,
    'rust': RUST_PATTERNS,
    'scala': SCALA_PATTERNS,
    'sql': SQL_PATTERNS,
    'squirrel': SQUIRREL_PATTERNS,
    'swift': SWIFT_PATTERNS,
    'vue': VUE_PATTERNS,
    'svelte': SVELTE_PATTERNS,
    'zig': ZIG_PATTERNS,
    'matlab': MATLAB_PATTERNS,
    'nim': NIM_PATTERNS,
    'cuda': CUDA_PATTERNS,
    'hcl': HCL_PATTERNS,
    'proto': PROTO_PATTERNS,
    'graphql': GRAPHQL_PATTERNS,
    'dockerfile': DOCKERFILE_PATTERNS,
    'cmake': CMAKE_PATTERNS,
    'toml': TOML_PATTERNS,
    'xml': XML_PATTERNS,
}

__all__ = ['query_patterns'] 