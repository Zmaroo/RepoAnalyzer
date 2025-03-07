"""Language mapping definitions and language detection utilities.

This module provides a comprehensive set of language mapping utilities, including:
1. Extensions to language mappings
2. Language aliases and normalization
3. Parser type determination
4. Language detection from content
5. Fallback mechanisms

All language detection logic should be centralized in this module.
"""
from utils.logger import log
from typing import Optional, Set, Dict, List, Tuple, Any, Union, Callable
import os
import re
import asyncio
from parsers.types import FileType, ParserType, AICapability, InteractionType, ConfidenceLevel
from parsers.models import LanguageFeatures
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorAudit, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator, cache_metrics
from utils.cache_analytics import get_cache_analytics, CacheAnalytics
from utils.request_cache import cached_in_request, request_cache_context, get_current_request_cache
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_operation
from db.transaction import transaction_scope
import time
import psutil

# Track initialization state and tasks
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()
_cache = None
_warmup_complete = False
_metrics = {
    "total_detections": 0,
    "successful_detections": 0,
    "failed_detections": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "detection_times": []
}

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """Initialize language mapping resources."""
    global _initialized, _cache
    if not _initialized:
        try:
            async with AsyncErrorBoundary("language_mapping_initialization"):
                # Initialize cache
                _cache = UnifiedCache("language_mapping")
                await cache_coordinator.register_cache(_cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    "language_mapping",
                    _warmup_cache
                )
                await analytics.optimize_ttl_values()
                
                # Initialize error analysis
                await ErrorAudit.analyze_codebase(os.path.dirname(__file__))
                
                # Register with health monitor
                global_health_monitor.register_component(
                    "language_mapping",
                    health_check=_check_health
                )
                
                # Start warmup task
                warmup_task = asyncio.create_task(_warmup_caches())
                _pending_tasks.add(warmup_task)
                
                # Validate mappings
                task = asyncio.create_task(validate_language_mappings())
                _pending_tasks.add(task)
                try:
                    errors = await task
                    if errors:
                        for error in errors:
                            log(error, level="warning")
                finally:
                    _pending_tasks.remove(task)
                
                _initialized = True
                log("Language mapping initialized", level="info")
        except Exception as e:
            log(f"Error initializing language mapping: {e}", level="error")
            raise

async def _warmup_caches():
    """Warm up caches with frequently used language mappings."""
    global _warmup_complete
    try:
        # Get frequently used languages
        async with transaction_scope() as txn:
            languages = await txn.fetch("""
                SELECT language_id, usage_count
                FROM language_usage_stats
                WHERE usage_count > 10
                ORDER BY usage_count DESC
                LIMIT 100
            """)
            
            # Warm up language cache
            for language in languages:
                await _warmup_cache([language["language_id"]])
                
        _warmup_complete = True
        await log("Language mapping cache warmup complete", level="info")
    except Exception as e:
        await log(f"Error warming up caches: {e}", level="error")

async def _warmup_cache(keys: List[str]) -> Dict[str, Any]:
    """Warmup function for language mapping cache."""
    results = {}
    for key in keys:
        try:
            language_info = await get_complete_language_info(key)
            if language_info:
                results[key] = language_info
        except Exception as e:
            await log(f"Error warming up language {key}: {e}", level="warning")
    return results

async def _check_health() -> Dict[str, Any]:
    """Health check for language mapping."""
    # Get error audit data
    error_report = await ErrorAudit.get_error_report()
    
    # Get cache analytics
    analytics = await get_cache_analytics()
    cache_stats = await analytics.get_metrics()
    
    # Get resource usage
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    # Calculate average detection time
    avg_detection_time = sum(_metrics["detection_times"]) / len(_metrics["detection_times"]) if _metrics["detection_times"] else 0
    
    # Calculate health status
    status = ComponentStatus.HEALTHY
    details = {
        "metrics": {
            "total_detections": _metrics["total_detections"],
            "success_rate": _metrics["successful_detections"] / _metrics["total_detections"] if _metrics["total_detections"] > 0 else 0,
            "cache_hit_rate": _metrics["cache_hits"] / (_metrics["cache_hits"] + _metrics["cache_misses"]) if (_metrics["cache_hits"] + _metrics["cache_misses"]) > 0 else 0,
            "avg_detection_time": avg_detection_time
        },
        "cache_stats": {
            "hit_rates": cache_stats.get("hit_rates", {}),
            "memory_usage": cache_stats.get("memory_usage", {}),
            "eviction_rates": cache_stats.get("eviction_rates", {})
        },
        "error_stats": {
            "total_errors": error_report.get("total_errors", 0),
            "error_rate": error_report.get("error_rate", 0),
            "top_errors": error_report.get("top_error_locations", [])[:3]
        },
        "resource_usage": {
            "memory_rss": memory_info.rss,
            "memory_vms": memory_info.vms,
            "cpu_percent": process.cpu_percent(),
            "thread_count": len(process.threads())
        },
        "warmup_status": {
            "complete": _warmup_complete,
            "cache_ready": _warmup_complete and _cache is not None
        }
    }
    
    # Check for degraded conditions
    if details["metrics"]["success_rate"] < 0.8:  # Less than 80% success rate
        status = ComponentStatus.DEGRADED
        details["reason"] = "Low detection success rate"
    elif error_report.get("error_rate", 0) > 0.1:  # More than 10% error rate
        status = ComponentStatus.DEGRADED
        details["reason"] = "High error rate"
    elif details["resource_usage"]["cpu_percent"] > 80:  # High CPU usage
        status = ComponentStatus.DEGRADED
        details["reason"] = "High CPU usage"
    elif avg_detection_time > 1.0:  # Average detection time > 1 second
        status = ComponentStatus.DEGRADED
        details["reason"] = "High detection times"
    elif not _warmup_complete:  # Cache not ready
        status = ComponentStatus.DEGRADED
        details["reason"] = "Cache warmup incomplete"
        
    return {
        "status": status,
        "details": details
    }

async def cleanup():
    """Clean up language mapping resources."""
    global _initialized, _cache
    try:
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        # Clean up cache
        if _cache:
            await _cache.clear_async()
            await cache_coordinator.unregister_cache("language_mapping")
        
        # Save error analysis
        await ErrorAudit.save_report()
        
        # Save cache analytics
        analytics = await get_cache_analytics()
        await analytics.save_metrics_history(_cache.get_metrics())
        
        # Save metrics to database
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_mapping_metrics (
                    timestamp, total_detections,
                    successful_detections, failed_detections,
                    cache_hits, cache_misses, avg_detection_time
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, (
                time.time(),
                _metrics["total_detections"],
                _metrics["successful_detections"],
                _metrics["failed_detections"],
                _metrics["cache_hits"],
                _metrics["cache_misses"],
                sum(_metrics["detection_times"]) / len(_metrics["detection_times"]) if _metrics["detection_times"] else 0
            ))
        
        # Unregister from health monitor
        global_health_monitor.unregister_component("language_mapping")
        
        _initialized = False
        _cache = None
        log("Language mapping cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up language mapping: {e}", level="error")
        raise ProcessingError(f"Failed to cleanup language mapping: {e}")

# Register cleanup handler
register_shutdown_handler(cleanup)

# Language support mappings
# --------------------------
# The following data structures work together to provide language support:
#
# 1. LANGUAGE_ALIASES - Maps alternate names to canonical language names
#    Used by: normalize_language_name()
#
# 2. EXTENSION_TO_LANGUAGE - Maps file extensions to canonical language names
#    Used by: detect_language_from_filename(), get_language_by_extension()
#
# 3. TREE_SITTER_LANGUAGES & CUSTOM_PARSER_LANGUAGES - Define available parser implementations
#    Used by: get_parser_type(), language_registry.get_parser()
#
# 4. LANGUAGE_TO_FILE_TYPE - Maps languages to their file type classification
#    Used by: get_file_type(), file classification
#
# 5. FILENAME_MAP - Maps specific filenames to language IDs
#    Used by: detect_language_from_filename()
#
# Validation is performed to ensure no language appears in both TREE_SITTER_LANGUAGES
# and CUSTOM_PARSER_LANGUAGES, as this would create ambiguity in parser selection.

# Language aliases map for normalization
LANGUAGE_ALIASES = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c#": "csharp",
    "cs": "csharp",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "py": "python",
    "pyi": "python",
    "pyc": "python",
    "rb": "ruby",
    "rake": "ruby",
    "gemspec": "ruby",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "shell": "bash",
    "htm": "html",
    "xhtml": "html",
    "yml": "yaml",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "gradle": "groovy",
    "markdown": "md",
    "rst": "restructuredtext",
    "rest": "restructuredtext",
    "asciidoc": "adoc",
    "ini": "properties",
    "conf": "properties",
    "cfg": "properties",
    "dockerfil": "dockerfile",
    "dockerfile": "dockerfile",
    "docker": "dockerfile",
    "mk": "make",
    "cmake": "cmake",
    "mak": "make",
    "el": "elisp",
    "emacs": "elisp",
    "emacslisp": "elisp",
    "ex": "elixir",
    "ml": "ocaml",
    "mli": "ocaml_interface",
}

# Core extension to language mapping (without period prefix)
EXTENSION_TO_LANGUAGE = {
    'py': 'python',
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'cpp': 'cpp',
    'hpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'c': 'c',
    'h': 'c',
    'rb': 'ruby',
    'php': 'php',
    'pl': 'perl',
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'scala': 'scala',
    'sc': 'scala',
    'sbt': 'scala',
    'groovy': 'groovy',
    'md': 'markdown',
    'markdown': 'markdown',
    'rst': 'restructuredtext',
    'adoc': 'asciidoc',
    'asciidoc': 'asciidoc',
    'tex': 'latex',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'toml': 'toml',
    'ini': 'ini',
    'conf': 'ini',
    'cfg': 'ini',
    'dockerfile': 'dockerfile',
    'makefile': 'make',
    'cmake': 'cmake',
    'swift': 'swift',
    'lua': 'lua',
    'r': 'r',
    'el': 'elisp',
    'ex': 'elixir',
    'exs': 'elixir',
    'heex': 'elixir',
    'leex': 'elixir',
    'lisp': 'commonlisp',
    'cl': 'commonlisp',
    'lsp': 'commonlisp',
    'cs': 'csharp',
    'cu': 'cuda',
    'cuh': 'cuda',
    'dart': 'dart',
    'dockerfil': 'dockerfile',
    'rake': 'ruby',
    'gemspec': 'ruby',
    'rs': 'rust',
    'rlib': 'rust',
    'sql': 'sql',
    'mysql': 'sql',
    'psql': 'sql',
    'swiftinterface': 'swift',
    'd.ts': 'typescript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'v': 'verilog',
    'vh': 'verilog',
    'sv': 'systemverilog',
    'svh': 'systemverilog',
    'vhd': 'vhdl',
    'vhdl': 'vhdl',
    'vho': 'vhdl',
    'vue': 'vue',
    'zig': 'zig',
    'elm': 'elm',
    'erl': 'erlang',
    'hrl': 'erlang',
    'fish': 'fish',
    'f90': 'fortran',
    'f95': 'fortran',
    'f03': 'fortran',
    'f08': 'fortran',
    'gd': 'gdscript',
    'gleam': 'gleam',
    'go': 'go',
    'hack': 'hack',
    'hh': 'hack',
    'hx': 'haxe',
    'hxml': 'haxe',
    'tf': 'hcl',
    'hcl': 'hcl',
    'tex': 'latex',
    'sty': 'latex',
    'cls': 'latex',
    'mk': 'make',
    'mak': 'make',
    'make': 'make',
    'm': 'matlab',
    'mat': 'matlab',
    'nix': 'nix',
    'mm': 'objc',
    'pas': 'pascal',
    'pp': 'pascal',
    'pm': 'perl',
    't': 'perl',
    'php4': 'php',
    'php5': 'php',
    'php7': 'php',
    'phps': 'php',
    'ps1': 'powershell',
    'psm1': 'powershell',
    'psd1': 'powershell',
    'prisma': 'prisma',
    'proto': 'proto',
    'purs': 'purescript',
    'qml': 'qmljs',
    'qmldir': 'qmldir',
    'rkt': 'racket',
    'txt': 'plaintext',
    'nut': 'squirrel',
    'star': 'starlark',
    'bzl': 'starlark',
    'svelte': 'svelte',
    'tcl': 'tcl',
    'tk': 'tcl',
    'sol': 'solidity',
    'ml': 'ocaml',
    'mli': 'ocaml_interface',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'css',
    'sass': 'css',
    'less': 'css',
    'xml': 'xml',
    'svg': 'xml',
    'graphql': 'graphql',
    'gql': 'graphql',
    'env': 'env',
    'editorconfig': 'editorconfig',
    'asm': 'asm',
    's': 'asm',
    'clj': 'clojure',
    'cob': 'cobalt',
    'jl': 'julia',
    'hs': 'haskell',
    'nim': 'nim',
    'bib': 'bibtex',
}

# Full extension map (with period prefix)
FULL_EXTENSION_MAP = {f'.{ext}': lang for ext, lang in EXTENSION_TO_LANGUAGE.items()}

# Files that should be recognized by filename rather than extension
FILENAME_MAP = {
    'makefile': 'make',
    'Makefile': 'make',
    'dockerfile': 'dockerfil',
    'Dockerfile': 'dockerfil',
    '.gitignore': 'gitignore',
    '.gitattributes': 'gitignore',
    'requirements.txt': 'requirements',
    'CMakeLists.txt': 'cmake',
    'package.json': 'json',
    'tsconfig.json': 'json',
    'composer.json': 'json',
    '.babelrc': 'json',
    '.npmrc': 'ini',
    '.eslintrc': 'json',
    'Gemfile': 'ruby',
    'Rakefile': 'ruby',
}

# Shebang pattern to detect language from script header
SHEBANG_PATTERN = re.compile(r'^#!\s*(?:/usr/bin/env\s+)?([a-zA-Z0-9_]+)')

# Shebang to language mapping
SHEBANG_MAP = {
    'python': 'python',
    'python2': 'python',
    'python3': 'python',
    'node': 'javascript',
    'nodejs': 'javascript',
    'bash': 'shell',
    'sh': 'shell',
    'zsh': 'shell',
    'ruby': 'ruby',
    'perl': 'perl',
    'php': 'php',
    'pwsh': 'powershell',
    'r': 'r',
}

# [2.1] Tree-sitter supported languages
TREE_SITTER_LANGUAGES = {
    "python": {
        "extensions": {".py", ".pyi", ".pyx", ".pxd"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    },
    "javascript": {
        "extensions": {".js", ".jsx", ".mjs"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    },
    "typescript": {
        "extensions": {".ts", ".tsx"},
        "parser_type": ParserType.TREE_SITTER,
        "file_type": FileType.CODE,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
    }
}

# [2.2] Custom parser supported languages
CUSTOM_PARSER_LANGUAGES = {
    "plaintext": {
        "extensions": {".txt", ".text", ".log"},
        "parser_type": ParserType.CUSTOM,
        "file_type": FileType.DOC,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.DOCUMENTATION
        }
    },
    "markdown": {
        "extensions": {".md", ".markdown", ".mdown"},
        "parser_type": ParserType.CUSTOM,
        "file_type": FileType.DOC,
        "ai_capabilities": {
            AICapability.CODE_UNDERSTANDING,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING
        }
    }
}

# [2.3] Language normalization mapping
LANGUAGE_NORMALIZATION = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "javascript",
    "tsx": "typescript",
    "md": "markdown",
    "txt": "plaintext"
}

async def normalize_language_name(language: str) -> str:
    """[2.4] Normalize a language name to its canonical form."""
    language = language.lower().strip()
    return LANGUAGE_NORMALIZATION.get(language, language)

async def get_parser_type(language: str) -> ParserType:
    """[2.5] Get the preferred parser type for a language."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["parser_type"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["parser_type"]
    
    return ParserType.UNKNOWN

async def get_file_type(language: str) -> FileType:
    """[2.6] Get the file type for a language."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["file_type"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["file_type"]
    
    return FileType.CODE

async def get_ai_capabilities(language: str) -> Set[AICapability]:
    """[2.7] Get AI capabilities supported by a language."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["ai_capabilities"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["ai_capabilities"]
    
    return {AICapability.CODE_UNDERSTANDING}

async def get_fallback_parser_type(language: str) -> Optional[ParserType]:
    """[2.8] Get the fallback parser type for a language."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return ParserType.CUSTOM
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return None
    
    return ParserType.UNKNOWN

async def get_language_features(language: str) -> Dict[str, Any]:
    """[2.9] Get comprehensive language features."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]
    
    return {
        "extensions": set(),
        "parser_type": ParserType.UNKNOWN,
        "file_type": FileType.CODE,
        "ai_capabilities": {AICapability.CODE_UNDERSTANDING}
    }

async def get_suggested_alternatives(language: str) -> List[str]:
    """[2.10] Get suggested alternative languages."""
    normalized = await normalize_language_name(language)
    
    language_families = {
        "javascript": ["typescript", "jsx"],
        "typescript": ["javascript", "tsx"],
        "python": ["nim", "cobra"],
        "markdown": ["asciidoc", "rst"],
        "plaintext": ["markdown", "rst"]
    }
    
    return language_families.get(normalized, [])

async def detect_language_from_filename(filename: str) -> Optional[str]:
    """[2.11] Detect language from filename."""
    # Track metrics
    start_time = time.time()
    _metrics["total_detections"] += 1
    
    try:
        # Check cache first
        if _cache:
            cache_key = f"filename:{filename}"
            cached_result = await _cache.get(cache_key)
            if cached_result:
                _metrics["cache_hits"] += 1
                return cached_result
            _metrics["cache_misses"] += 1
        
        # Check exact filename matches first
        if filename in FILENAME_MAP:
            language_id = FILENAME_MAP[filename]
            _metrics["successful_detections"] += 1
            if _cache:
                await _cache.set(cache_key, language_id)
            return language_id
        
        # Check extension
        ext = os.path.splitext(filename)[1].lower()
        
        # Check tree-sitter languages
        for lang, info in TREE_SITTER_LANGUAGES.items():
            if ext in info["extensions"]:
                _metrics["successful_detections"] += 1
                if _cache:
                    await _cache.set(cache_key, lang)
                return lang
        
        # Check custom parser languages
        for lang, info in CUSTOM_PARSER_LANGUAGES.items():
            if ext in info["extensions"]:
                _metrics["successful_detections"] += 1
                if _cache:
                    await _cache.set(cache_key, lang)
                return lang
        
        _metrics["failed_detections"] += 1
        return None
    finally:
        _metrics["detection_times"].append(time.time() - start_time)

async def detect_language_from_content(content: str) -> Optional[str]:
    """[2.12] Detect language from content with metrics tracking."""
    # Track metrics
    start_time = time.time()
    _metrics["total_detections"] += 1
    
    try:
        # Check cache first
        if _cache:
            cache_key = f"content:{hash(content)}"
            cached_result = await _cache.get(cache_key)
            if cached_result:
                _metrics["cache_hits"] += 1
                return cached_result
            _metrics["cache_misses"] += 1
        
        if not content or not content.strip():
            _metrics["failed_detections"] += 1
            return None
        
        # Check for shebang
        if content.startswith('#!'):
            match = SHEBANG_PATTERN.match(content)
            if match:
                interpreter = match.group(1).lower()
                if interpreter in SHEBANG_MAP:
                    language_id = SHEBANG_MAP[interpreter]
                    _metrics["successful_detections"] += 1
                    if _cache:
                        await _cache.set(cache_key, language_id)
                    return language_id
        
        # Rest of the content detection logic...
        # (Keep existing detection logic but add caching and metrics)
        
        _metrics["failed_detections"] += 1
        return None
    finally:
        _metrics["detection_times"].append(time.time() - start_time)

async def detect_language(file_path: str, content: Optional[str] = None) -> Tuple[str, float, bool]:
    """
    Unified language detection that combines filename and content analysis with confidence scoring.
    
    Args:
        file_path: Path to the file
        content: Optional file content for more accurate detection
        
    Returns:
        Tuple of (language_id, confidence_score, is_binary)
    """
    if not _initialized:
        await initialize()
    
    # Track metrics
    start_time = time.time()
    _metrics["total_detections"] += 1
    
    try:
        # Check cache first
        if _cache:
            cache_key = f"unified:{file_path}:{hash(content) if content else ''}"
            cached_result = await _cache.get(cache_key)
            if cached_result:
                _metrics["cache_hits"] += 1
                return cached_result
            _metrics["cache_misses"] += 1
        
        # Check if binary first
        is_binary = False
        _, ext = os.path.splitext(file_path)
        if ext in BINARY_EXTENSIONS:
            is_binary = True
        elif content:
            try:
                is_binary = (b"\x00" in content.encode("utf-8") or 
                            sum(1 for c in content if not (32 <= ord(c) <= 126)) > len(content) * 0.3)
            except UnicodeEncodeError:
                is_binary = True
        
        # Try filename detection first
        language_id = await detect_language_from_filename(file_path)
        if language_id:
            result = (language_id, 0.9, is_binary)
            _metrics["successful_detections"] += 1
            if _cache:
                await _cache.set(cache_key, result)
            return result
        
        # Try content detection if available
        if content and not is_binary:
            language_id = await detect_language_from_content(content)
            if language_id:
                result = (language_id, 0.7, is_binary)
                _metrics["successful_detections"] += 1
                if _cache:
                    await _cache.set(cache_key, result)
                return result
        
        # Fallback to unknown with low confidence
        _metrics["failed_detections"] += 1
        result = ("unknown", 0.1, is_binary)
        if _cache:
            await _cache.set(cache_key, result)
        return result
    finally:
        _metrics["detection_times"].append(time.time() - start_time)

async def get_extensions_for_language(language: str) -> Set[str]:
    """[2.12] Get file extensions for a language."""
    normalized = await normalize_language_name(language)
    
    if normalized in TREE_SITTER_LANGUAGES:
        return TREE_SITTER_LANGUAGES[normalized]["extensions"]
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        return CUSTOM_PARSER_LANGUAGES[normalized]["extensions"]
    
    return set()

async def get_complete_language_info(language: str) -> Dict[str, Any]:
    """[2.13] Get complete language information."""
    normalized = await normalize_language_name(language)
    
    base_info = {
        "canonical_name": normalized,
        "parser_type": await get_parser_type(normalized),
        "file_type": await get_file_type(normalized),
        "extensions": await get_extensions_for_language(normalized),
        "ai_capabilities": await get_ai_capabilities(normalized),
        "fallback_parser_type": await get_fallback_parser_type(normalized),
        "alternatives": await get_suggested_alternatives(normalized),
        "tree_sitter_available": normalized in TREE_SITTER_LANGUAGES,
        "custom_parser_available": normalized in CUSTOM_PARSER_LANGUAGES
    }
    
    if normalized in TREE_SITTER_LANGUAGES:
        base_info.update(TREE_SITTER_LANGUAGES[normalized])
    elif normalized in CUSTOM_PARSER_LANGUAGES:
        base_info.update(CUSTOM_PARSER_LANGUAGES[normalized])
    
    return base_info

async def is_supported_language(language: str) -> bool:
    """Check if a language is supported by any parser."""
    normalized = await normalize_language_name(language)
    return (normalized in TREE_SITTER_LANGUAGES or 
            normalized in CUSTOM_PARSER_LANGUAGES or
            normalized in EXTENSION_TO_LANGUAGE.values())

async def get_supported_languages() -> Dict[str, ParserType]:
    """Get a dictionary of all supported languages and their parser types."""
    languages = {}
    
    for lang in TREE_SITTER_LANGUAGES:
        languages[lang] = ParserType.TREE_SITTER
    
    for lang in CUSTOM_PARSER_LANGUAGES:
        languages[lang] = ParserType.CUSTOM
    
    return languages

async def get_supported_extensions() -> Dict[str, str]:
    """Get a dictionary of all supported file extensions."""
    return EXTENSION_TO_LANGUAGE

# MIME type mappings for common languages
MIME_TYPES: Dict[str, str] = {
    'python': 'text/x-python',
    'javascript': 'application/javascript',
    'typescript': 'application/typescript',
    'java': 'text/x-java-source',
    'c': 'text/x-c',
    'cpp': 'text/x-c++',
    'go': 'text/x-go',
    'rust': 'text/x-rust',
    'ruby': 'text/x-ruby',
    'php': 'text/x-php',
    'html': 'text/html',
    'css': 'text/css',
    'json': 'application/json',
    'yaml': 'text/yaml',
    'xml': 'text/xml',
    'markdown': 'text/markdown',
    'shell': 'text/x-shellscript',
    'sql': 'text/x-sql'
}

# Language to file type mappings
LANGUAGE_TO_FILE_TYPE: Dict[str, FileType] = {
    'python': FileType.CODE,
    'javascript': FileType.CODE,
    'typescript': FileType.CODE,
    'java': FileType.CODE,
    'c': FileType.CODE,
    'cpp': FileType.CODE,
    'go': FileType.CODE,
    'rust': FileType.CODE,
    'ruby': FileType.CODE,
    'php': FileType.CODE,
    'html': FileType.MARKUP,
    'css': FileType.STYLE,
    'json': FileType.DATA,
    'yaml': FileType.DATA,
    'xml': FileType.MARKUP,
    'markdown': FileType.DOCUMENTATION,
    'shell': FileType.SCRIPT,
    'sql': FileType.QUERY,
    'text': FileType.TEXT,
    'binary': FileType.BINARY,
    'unknown': FileType.UNKNOWN
}

# Binary file extensions
BINARY_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd',  # Python
    '.o', '.obj', '.a', '.lib', '.so', '.dll', '.dylib',  # C/C++
    '.class', '.jar',  # Java
    '.exe', '.bin',  # Executables
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp',  # Images
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',  # Documents
    '.zip', '.tar', '.gz', '.7z', '.rar',  # Archives
    '.ttf', '.otf', '.woff', '.woff2',  # Fonts
    '.mp3', '.mp4', '.wav', '.avi',  # Media
    '.db', '.sqlite', '.sqlite3'  # Databases
}

async def validate_language_mappings() -> List[str]:
    """
    Validate the consistency of all language mappings and return any inconsistencies found.
    
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Check for languages in TREE_SITTER_LANGUAGES or CUSTOM_PARSER_LANGUAGES but not in EXTENSION_TO_LANGUAGE
    ts_missing = [lang for lang in TREE_SITTER_LANGUAGES 
                 if lang not in EXTENSION_TO_LANGUAGE.values() and lang not in LANGUAGE_ALIASES.values()]
    if ts_missing:
        errors.append(f"Languages in TREE_SITTER_LANGUAGES without extension mappings: {', '.join(ts_missing)}")
    
    custom_missing = [lang for lang in CUSTOM_PARSER_LANGUAGES 
                     if lang not in EXTENSION_TO_LANGUAGE.values() and lang not in LANGUAGE_ALIASES.values()]
    if custom_missing:
        errors.append(f"Languages in CUSTOM_PARSER_LANGUAGES without extension mappings: {', '.join(custom_missing)}")
    
    # Check for languages with conflicting file type mappings
    for lang, file_type in LANGUAGE_TO_FILE_TYPE.items():
        if lang in TREE_SITTER_LANGUAGES or lang in CUSTOM_PARSER_LANGUAGES:
            # Good, language is supported
            pass
        else:
            errors.append(f"Language '{lang}' has file type mapping but no parser support")
    
    return errors
