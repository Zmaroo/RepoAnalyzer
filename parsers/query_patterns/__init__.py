"""Query patterns package."""

from .ada import ADA_PATTERNS
from .clojure import CLOJURE_PATTERNS
from .common import JS_TS_SHARED_PATTERNS
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
from .racket import RACKET_PATTERNS
from .ruby import RUBY_PATTERNS
from .rust import RUST_PATTERNS
from .scala import SCALA_PATTERNS
from .sql import SQL_PATTERNS
from .squirrel import SQUIRREL_PATTERNS
from .swift import SWIFT_PATTERNS
from .typescript import TS_PATTERNS

# Export all patterns in a dictionary
QUERY_PATTERNS = {
    'ada': ADA_PATTERNS,
    'clojure': CLOJURE_PATTERNS,
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
    'racket': RACKET_PATTERNS,
    'ruby': RUBY_PATTERNS,
    'rust': RUST_PATTERNS,
    'scala': SCALA_PATTERNS,
    'sql': SQL_PATTERNS,
    'squirrel': SQUIRREL_PATTERNS,
    'swift': SWIFT_PATTERNS,
    'typescript': TS_PATTERNS,
    'javascript': JS_TS_SHARED_PATTERNS
}

__all__ = ['QUERY_PATTERNS'] 