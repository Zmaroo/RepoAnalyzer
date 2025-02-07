"""Tree-sitter query patterns for all supported languages."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from parsers.file_parser import EXTENSION_TO_LANGUAGE
from utils.logger import logger
from .query_patterns import QUERY_PATTERNS

# Tree-sitter query patterns for all supported languages
query_patterns = {}

# Get unique set of languages from extension mappings
supported_languages = set(EXTENSION_TO_LANGUAGE.values())

# Define language aliases mapping to normalized keys in QUERY_PATTERNS.
ALIASES = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "c#": "csharp",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "typescriptreact": "tsx",
    "golang": "go",
    "py": "python",
    "rb": "ruby",
    # Add additional aliases as needed
}

def normalize_language_name(lang_name: str) -> str:
    """
    Normalize the given language name to match the keys in QUERY_PATTERNS.
    This function converts the language name to lowercase, removes dashes and underscores,
    and applies common alias mappings for languages.
    """
    lang_lower = lang_name.lower().strip()
    # Check direct alias on the lower-cased name.
    if lang_lower in ALIASES:
        return ALIASES[lang_lower]
    
    # Remove dashes and underscores for further normalization.
    normalized = lang_lower.replace('-', '').replace('_', '')
    if normalized in ALIASES:
        return ALIASES[normalized]
    
    # Replace specific characters for more accurate normalization.
    normalized = normalized.replace('++', 'pp').replace('#', 'sharp')
    return normalized

def get_query_patterns(lang_name: str):
    """
    Retrieve the query patterns for the given language name.
    
    Args:
        lang_name (str): The input language name (e.g. 'C++', 'Python', 'js', etc.)
    
    Returns:
        dict: The query patterns corresponding to the normalized language name.
    
    Raises:
        ValueError: If the language is not supported.
    """
    normalized_name = normalize_language_name(lang_name)
    if normalized_name in QUERY_PATTERNS:
        return QUERY_PATTERNS[normalized_name]
    else:
        raise ValueError(f"Unsupported language: {lang_name}")

# Dynamically populate patterns for each supported language
for lang_name in supported_languages:
    try:
        # Convert language name to our standardized format (e.g., 'c-sharp' -> 'csharp')
        normalized_name = normalize_language_name(lang_name)
        
        # Skip any languages we don't have patterns for yet
        if normalized_name not in [
            'ada', 'clojure', 'cpp', 'csharp', 'go', 'groovy', 'haskell',
            'java', 'kotlin', 'lua', 'objectivec', 'perl', 'php', 'powershell',
            'python', 'racket', 'ruby', 'rust', 'scala', 'sql', 'squirrel',
            'swift', 'typescript', 'javascript'
        ]:
            continue
            
        # Import the appropriate patterns module
        patterns_module = __import__(
            f'parsers.query_patterns.{normalized_name}',
            fromlist=[f'{normalized_name.upper()}_PATTERNS']
        )
        
        # Get the patterns for this language
        patterns = getattr(patterns_module, f'{normalized_name.upper()}_PATTERNS')
        
        # Add to our patterns dictionary
        query_patterns[normalized_name] = patterns
        
    except Exception as e:
        # Log warning but continue - some languages might not have patterns yet
        logger.warning(f"Could not load patterns for {lang_name}: {e}")

# Handle special cases like markup languages
from parsers.query_patterns.markup import (
    HTML_PATTERNS, YAML_PATTERNS, TOML_PATTERNS,
    DOCKERFILE_PATTERNS, MARKDOWN_PATTERNS,
    REQUIREMENTS_PATTERNS, GITIGNORE_PATTERNS,
    MAKEFILE_PATTERNS
)

query_patterns['markup'] = {
    'html': HTML_PATTERNS,
    'yaml': YAML_PATTERNS,
    'toml': TOML_PATTERNS,
    'dockerfile': DOCKERFILE_PATTERNS,
    'markdown': MARKDOWN_PATTERNS,
    'requirements': REQUIREMENTS_PATTERNS,
    'gitignore': GITIGNORE_PATTERNS,
    'makefile': MAKEFILE_PATTERNS
}