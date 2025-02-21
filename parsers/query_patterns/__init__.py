import os
import importlib
import pkgutil
from parsers.language_mapping import normalize_language_name
from utils.logger import log
from utils.encoding import encode_query_patterns
from parsers.file_classification import FileType, FileClassification

# Define pattern categories with language-specific patterns
PATTERN_CATEGORIES = {
    "syntax": {
        FileType.CODE: [
            "interface", "type_alias", "enum", "decorator",
            "function", "class", "module", "method", "constructor",
            "interface", "enum", "struct", "union", "typedef"
        ],
        FileType.DOC: [
            "section", "block", "element", "directive",
            "macro", "attribute", "heading", "list", "table"
        ]
    },
    "semantics": {
        FileType.CODE: [
            "type_assertion", "type_predicate", "type_query",
            "union_type", "intersection_type", "tuple_type",
            "variable", "type", "expression", "parameter",
            "return_type", "generic", "template", "operator"
        ],
        FileType.DOC: [
            "link", "reference", "definition", "term",
            "callout", "citation", "footnote", "glossary"
        ]
    },
    "documentation": {
        FileType.CODE: [
            "comment", "docstring", "javadoc", "xmldoc",
            "todo", "fixme", "note", "warning"
        ],
        FileType.DOC: [
            "metadata", "description", "admonition",
            "annotation", "field", "example", "tip", "caution"
        ]
    },
    "structure": {
        FileType.CODE: [
            "namespace", "import", "export", "package",
            "using", "include", "require", "module_import"
        ],
        FileType.DOC: [
            "hierarchy", "include", "anchor", "toc",
            "cross_reference", "bibliography", "appendix"
        ]
    }
}

# Move query pattern loading to a dedicated function
def load_query_patterns() -> dict:
    """Load all query patterns from the patterns directory"""
    patterns = {}
    package_dir = os.path.dirname(__file__)
    
    for module_info in pkgutil.iter_modules([package_dir]):
        module_name = module_info.name
        if module_name == '__init__':
            continue
            
        try:
            module = importlib.import_module(f"parsers.query_patterns.{module_name}")
            for attr in dir(module):
                if attr.endswith('_PATTERNS'):
                    module_patterns = getattr(module, attr)
                    if isinstance(module_patterns, (dict, list)):
                        key = normalize_language_name(module_name.lower())
                        if isinstance(module_patterns, dict):
                            for category in module_patterns:
                                if isinstance(module_patterns[category], dict):
                                    for pattern_name, pattern in module_patterns[category].items():
                                        if isinstance(pattern, dict) and "pattern" in pattern:
                                            module_patterns[category][pattern_name] = pattern["pattern"]
                        patterns[key] = module_patterns
                        log(f"Loaded query patterns for '{key}' from attribute '{attr}'", level="debug")
        except Exception as e:
            log(f"Failed to import query patterns module '{module_name}': {e}", level="error")
            
    return patterns

# Initialize patterns once at module load
QUERY_PATTERNS = load_query_patterns()

def get_patterns_for_file(file_classification: FileClassification) -> dict:
    """Get appropriate patterns based on file classification"""
    patterns = {}
    file_type = file_classification.file_type
    
    # Get base patterns for the file type
    for category, type_patterns in PATTERN_CATEGORIES.items():
        if file_type in type_patterns:
            patterns[category] = type_patterns[file_type]
    
    # Add language-specific patterns if defined
    language = file_classification.parser
    language_patterns = QUERY_PATTERNS.get(language, {})
    
    # Merge and categorize language-specific patterns
    for pattern_name, pattern in language_patterns.items():
        category = validate_pattern_category(pattern_name, file_type)
        if category != "unknown":
            if category not in patterns:
                patterns[category] = []
            patterns[category].append(pattern)
    
    return patterns

def validate_pattern_category(pattern_name: str, file_type: FileType) -> str:
    """Validate and return the category a pattern belongs to based on file type"""
    for category, type_patterns in PATTERN_CATEGORIES.items():
        if file_type in type_patterns and any(
            pattern in pattern_name 
            for pattern in type_patterns[file_type]
        ):
            return category
    return "unknown"