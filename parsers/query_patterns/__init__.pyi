from typing import Dict, Any, List, Optional, Callable, Union, TypeVar, Set
from parsers.types import PatternCategory, QueryPattern, PatternInfo

def _normalize_language_name(language: str) -> str: ...

def get_pattern_module(language_id: str) -> Optional[Any]: ...

def _ensure_pattern_category_keys(patterns_dict: Dict[str, Any]) -> Dict[PatternCategory, Any]: ...

def get_patterns_for_language(language: str) -> Dict[str, Any]: ...

def get_typed_patterns_for_language(language: str) -> Dict[PatternCategory, Dict[str, QueryPattern]]: ...

def register_common_patterns() -> Dict[str, Any]: ...

def list_available_languages() -> Set[str]: ...

def initialize_pattern_system() -> None: ...

def get_all_available_patterns() -> Dict[str, Dict[str, Any]]: ...

def clear_pattern_cache() -> None: ...

def validate_loaded_patterns() -> str: ... 