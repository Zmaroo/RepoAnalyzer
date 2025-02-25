"""Unified parsing interface.

Pipeline Stages:
1. File Classification & Parser Selection
   Input: file_path (str), content (str)
   - Uses: parsers/file_classification.py -> get_file_classification()
     Returns: Optional[FileClassification]
   - Uses: parsers/language_support.py -> language_registry.get_parser()
     Returns: Optional[BaseParser]

2. Content Parsing
   Input: encoded_content (str)
   - Uses: parsers/base_parser.py -> BaseParser.parse()
     Returns: Optional[ParserResult]
   - Uses: utils/encoding.py -> encode_query_pattern()
     Returns: str

3. Feature Extraction
   Input: ast (Dict[str, Any]), source_code (str)
   - Uses: parsers/base_parser.py -> BaseParser._extract_features()
     Returns: ExtractedFeatures
   - Uses: parsers/pattern_processor.py -> pattern_processor.get_patterns_for_file()
     Returns: Dict[str, Dict[str, ProcessedPattern]]

4. Result Standardization
   Input: ParserResult, ExtractedFeatures
   - Uses: parsers/models.py -> ParserResult
   - Uses: utils/cache.py -> parser_cache
   Returns: Optional[ParserResult]
"""

from typing import Optional
from .types import FileType, FeatureCategory, ParserType
from .models import FileClassification, ParserResult, PATTERN_CATEGORIES

from parsers.language_support import language_registry, get_language_by_extension
from parsers.feature_extractor import FeatureExtractor
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ParsingError
from utils.encoding import encode_query_pattern
from utils.logger import log
from utils.cache import parser_cache

class UnifiedParser:
    """Unified parsing interface."""
    
    @handle_async_errors(error_types=(ParsingError, Exception))
    async def parse_file(self, file_path: str, content: str) -> Optional[ParserResult]:
        """Parse file content using appropriate parser."""
        try:
            # [1.1] Cache Check
            # USES: [utils/cache.py] parser_cache.get_async() -> Optional[Dict]
            cache_key = f"parse:{file_path}:{hash(content)}"
            cached = await parser_cache.get_async(cache_key)
            if cached:
                return ParserResult(**cached)  # USES: [models.py] ParserResult

            # [1.2] Language Detection
            # USES: [language_support.py] get_language_by_extension() -> Optional[LanguageFeatures]
            language_features = get_language_by_extension(file_path)
            if not language_features:
                return None

            # [1.3] Classification Creation
            # USES: [models.py] FileClassification, FileType, ParserType
            classification = FileClassification(
                file_type=FileType.CODE,
                language_id=language_features.canonical_name,
                parser_type="tree_sitter"  # or "custom" per your logic.
            )

            # [2.1] Get Parser Instance
            # USES: [language_support.py] language_registry.get_parser() -> Optional[BaseParser]
            parser = language_registry.get_parser(classification)
            if not parser:
                log(f"No parser found for language: {classification.language_id}", level="error")
                return None

            # [2.2] Parse Content
            # USES: [utils/encoding.py] encode_query_pattern() -> str
            # USES: [base_parser.py] BaseParser.parse() -> Optional[ParserResult]
            parse_result = parser.parse(content)
            if not parse_result or not parse_result.success:
                return None

            # Stage 3: Extract features by category
            features = {}
            for category in FeatureCategory:
                category_features = parser._extract_category_features(
                    category=category,
                    ast=parse_result.ast,
                    source_code=content
                )
                features[category.value] = category_features

            # Stage 4: Create categorized result
            result = ParserResult(
                success=True,
                ast=parse_result.ast,
                features={
                    "syntax": features[FeatureCategory.SYNTAX.value],
                    "semantics": features[FeatureCategory.SEMANTICS.value],
                    "documentation": features[FeatureCategory.DOCUMENTATION.value],
                    "structure": features[FeatureCategory.STRUCTURE.value]
                },
                documentation=features[FeatureCategory.DOCUMENTATION.value],
                complexity=features[FeatureCategory.SYNTAX.value].get("metrics", {}),
                statistics=parse_result.statistics
            )
            
            # Cache result
            await parser_cache.set_async(cache_key, result.model_dump())
            return result

        except Exception as e:
            log(f"Error parsing file {file_path}: {e}", level="error")
            return None

# Global instance
unified_parser = UnifiedParser() 