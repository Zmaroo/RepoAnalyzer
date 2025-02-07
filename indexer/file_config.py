from parsers.file_parser import EXTENSION_TO_LANGUAGE
from parsers.query_patterns import QUERY_PATTERNS
from functools import lru_cache

# Define a static set for documentation extensions
DOC_EXTENSIONS_STATIC = {'.md', '.txt', '.rst'}

# Custom classification for markup file extensions
MARKUP_CLASSIFICATION = {
    '.html': 'code',
    '.xml': 'code',
    '.md': 'doc',         # Markdown files as docs
    '.yml': 'doc',
    '.yaml': 'doc',
    '.toml': 'doc',
    '.dockerfile': 'code',
    '.gitignore': 'doc',
    '.makefile': 'code'
}

@lru_cache(maxsize=1)
def get_supported_extensions():
    """
    Computes which file extensions should be processed as code files
    or documentation files based on the language mappings.
    Caches the result on first computation.
    
    Returns:
        A tuple (code_extensions, doc_extensions) where each is a set of extensions.
    """
    code_ext = set()
    doc_ext = set()

    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        normalized_lang = lang.replace('-', '').lower()
        ext_with_dot = f".{ext.lower()}" if not ext.startswith('.') else ext.lower()
        if normalized_lang in QUERY_PATTERNS or normalized_lang == 'markup':
            if normalized_lang == 'markup':
                if ext_with_dot in MARKUP_CLASSIFICATION:
                    if MARKUP_CLASSIFICATION[ext_with_dot] == 'code':
                        code_ext.add(ext_with_dot)
                    else:
                        doc_ext.add(ext_with_dot)
                else:
                    # Fallback: check against static doc extensions
                    if ext_with_dot in DOC_EXTENSIONS_STATIC:
                        doc_ext.add(ext_with_dot)
                    else:
                        code_ext.add(ext_with_dot)
            else:
                if ext_with_dot in DOC_EXTENSIONS_STATIC:
                    doc_ext.add(ext_with_dot)
                else:
                    code_ext.add(ext_with_dot)
    return (code_ext, doc_ext)

CODE_EXTENSIONS, DOC_EXTENSIONS = get_supported_extensions() 