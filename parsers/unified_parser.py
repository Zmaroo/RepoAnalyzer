"""Unified parsing interface.

Pipeline Stages:
1. File Classification & Parser Selection
   - Uses: parsers/file_classification.py -> get_file_classification()
     Returns: Optional[FileClassification]
   - Uses: parsers/language_support.py -> language_registry.get_parser()
     Returns: Optional[BaseParser]

2. Content Parsing
   - Uses: parsers/base_parser.py -> BaseParser.parse()
     Returns: Optional[ParserResult]

3. Feature Extraction
   - Uses: parsers/base_parser.py -> BaseParser._extract_category_features()
     Returns: ExtractedFeatures

4. Result Standardization
   - Returns: Optional[ParserResult]
"""

from typing import Optional
from parsers.types import FileType, FeatureCategory, ParserType, ParserResult
from parsers.models import FileClassification, PATTERN_CATEGORIES
from dataclasses import asdict

from parsers.language_support import language_registry
from parsers.language_mapping import (
    detect_language, 
    get_parser_info_for_language, 
    get_complete_language_info
)
from utils.error_handling import handle_async_errors, ParsingError
from utils.encoding import encode_query_pattern
from utils.logger import log
from utils.cache import parser_cache

class UnifiedParser:
    """Unified parsing interface."""
    
    @handle_async_errors(error_types=(ParsingError, Exception))
    async def parse_file(self, file_path: str, content: str) -> Optional[ParserResult]:
        """Parse file content using appropriate parser."""
        try:
            cache_key = f"parse:{file_path}:{hash(content)}"
            cached = await parser_cache.get_async(cache_key)
            if cached:
                return ParserResult(**cached)
            
            # Use the improved language detection with confidence score
            language_id, confidence = detect_language(file_path, content)
            if confidence < 0.6:
                log(f"Low confidence ({confidence:.2f}) language detection for {file_path}", level="warning")
            
            # Get comprehensive language and parser information
            language_info = get_complete_language_info(language_id)
            
            # Create classification using the parser info
            classification = FileClassification(
                file_type=language_info["file_type"],
                language_id=language_info["canonical_name"],
                parser_type=language_info["parser_type"]
            )

            parser = language_registry.get_parser(classification)
            if not parser:
                log(f"No parser found for language: {classification.language_id}", level="error")
                return None

            parse_result = parser.parse(content)
            if not parse_result or not parse_result.success:
                return None

            features = {}
            for category in FeatureCategory:
                category_features = parser._extract_category_features(
                    category=category,
                    ast=parse_result.ast,
                    source_code=content
                )
                features[category.value] = category_features

            result = ParserResult(
                success=True,
                ast=parse_result.ast,
                features={
                    "syntax": features.get(FeatureCategory.SYNTAX.value, {}),
                    "semantics": features.get(FeatureCategory.SEMANTICS.value, {}),
                    "documentation": features.get(FeatureCategory.DOCUMENTATION.value, {}),
                    "structure": features.get(FeatureCategory.STRUCTURE.value, {})
                },
                documentation=features.get(FeatureCategory.DOCUMENTATION.value, {}),
                complexity=features.get(FeatureCategory.SYNTAX.value, {}).get("metrics", {}),
                statistics=parse_result.statistics
            )

            cached_result = asdict(result)
            await parser_cache.set_async(cache_key, cached_result)
            return result

        except Exception as e:
            log(f"Error parsing file {file_path}: {e}", level="error")
            return None

# Global instance
unified_parser = UnifiedParser() 