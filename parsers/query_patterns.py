"""Tree-sitter query patterns for all supported languages."""

from tree_sitter_language_pack import get_binding, get_language, get_parser
from parsers.file_parser import EXTENSION_TO_LANGUAGE
from utils.logger import logger

# Tree-sitter query patterns for all supported languages
query_patterns = {}

# Get unique set of languages from extension mappings
supported_languages = set(EXTENSION_TO_LANGUAGE.values())

# Dynamically populate patterns for each supported language
for lang_name in supported_languages:
    try:
        # Convert language name to our standardized format (e.g., 'c-sharp' -> 'csharp')
        normalized_name = lang_name.replace('-', '').lower()
        
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