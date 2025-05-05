"""Unified parser management.

This module provides a unified interface for all parsers,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    ParserResult, PatternValidationResult, AIProcessingResult
)
from parsers.base_parser import BaseParser
from parsers.parser_interfaces import BaseParserInterface
from parsers.tree_sitter_parser import get_tree_sitter_parser
from parsers.language_config import get_language_config
from parsers.language_mapping import get_language_mapping, LanguageMapping
from parsers.language_support import get_language_support
from parsers.feature_extractor import get_feature_extractor
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope
import traceback

@dataclass
class UnifiedParser(BaseParser):
    """Unified parser management.
    
    This class provides a unified interface for all parsers,
    integrating with the parser system for efficient parsing.
    
    Attributes:
        language_id (str): The identifier for the language
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): The type of parser implementation
        _parsers (Dict[str, BaseParser]): Map of language IDs to parser instances
    """
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize unified parser.
        
        Args:
            language_id: The identifier for the language
            file_type: The type of files this parser can process
            parser_type: The type of parser implementation
        """
        super().__init__(
            language_id=language_id,
            file_type=file_type,
            parser_type=parser_type
        )
        self._parsers = {}
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize unified parser.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"unified_parser_initialization_{self.language_id}"):
                # Initialize components through async_runner
                init_task = submit_async_task(self._initialize_components())
                await asyncio.wrap_future(init_task)
                
                if not self._parsers:
                    raise ProcessingError(f"Failed to initialize parsers for {self.language_id}")
                
                await log(f"Unified parser initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing unified parser: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_parser_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"unified_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"parser_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize unified parser for {self.language_id}: {e}")
    
    async def _initialize_components(self) -> None:
        """Initialize parser components."""
        try:
            async with AsyncErrorBoundary(f"initialize_components_{self.language_id}",
                                         error_types=(ProcessingError,),
                                         severity=ErrorSeverity.CRITICAL):
                # Update health status
                await global_health_monitor.update_component_status(
                    f"unified_parser_{self.language_id}",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "component_initialization"}
                )
                
                # Get language configuration
                config = await get_language_config(self.language_id)
                if not config:
                    raise ProcessingError(f"Failed to get language configuration for {self.language_id}")
                
                # Get language mapping
                mapping = await get_language_mapping(self.language_id)
                if not mapping:
                    raise ProcessingError(f"Failed to get language mapping for {self.language_id}")
                
                # Get language support
                support = await get_language_support(self.language_id)
                if not support:
                    raise ProcessingError(f"Failed to get language support for {self.language_id}")
                
                # Get feature extractor
                extractor = await get_feature_extractor(self.language_id)
                if not extractor:
                    raise ProcessingError(f"Failed to get feature extractor for {self.language_id}")
                
                # Get tree-sitter parser if supported
                has_tree_sitter = False
                if support.level.supports_tree_sitter:
                    await log(f"Initializing tree-sitter parser for {self.language_id}", 
                             level="info",
                             context={
                                 "component": "unified_parser",
                                 "language_id": self.language_id,
                                 "operation": "initialize_components"
                             })
                    
                    parser_task = submit_async_task(get_tree_sitter_parser(self.language_id))
                    try:
                        parser = await asyncio.wrap_future(parser_task)
                        if parser:
                            self._parsers["tree_sitter"] = parser
                            has_tree_sitter = True
                            await log(f"Tree-sitter parser initialized for {self.language_id}", level="info")
                    except Exception as e:
                        await log(f"Failed to initialize tree-sitter parser: {e}", 
                                 level="warning",
                                 context={
                                     "component": "unified_parser",
                                     "language_id": self.language_id,
                                     "error": str(e)
                                 })
                
                # Get custom parser if tree-sitter is not available
                if not has_tree_sitter:
                    await log(f"Tree-sitter not available for {self.language_id}, trying custom parser", 
                             level="info",
                             context={
                                 "component": "unified_parser",
                                 "language_id": self.language_id,
                                 "operation": "initialize_components"
                             })
                    
                    # Import here to avoid circular imports
                    from parsers.custom_parsers import get_custom_parser_classes, CUSTOM_PARSER_CLASSES
                    if self.language_id in get_custom_parser_classes():
                        await log(f"Custom parser available for {self.language_id}, initializing", level="info")
                        
                        # Get the parser class and create instance
                        custom_parser_class = CUSTOM_PARSER_CLASSES.get(self.language_id)
                        if custom_parser_class:
                            try:
                                custom_parser_task = submit_async_task(
                                    custom_parser_class.create(
                                        language_id=self.language_id,
                                        file_type=self.file_type,
                                        parser_type=ParserType.CUSTOM
                                    )
                                )
                                parser = await asyncio.wrap_future(custom_parser_task)
                                if parser:
                                    self._parsers["custom"] = parser
                                    await log(f"Custom parser initialized for {self.language_id}", level="info")
                            except Exception as e:
                                await log(f"Failed to initialize custom parser: {e}", 
                                         level="warning",
                                         context={
                                             "component": "unified_parser",
                                             "language_id": self.language_id,
                                             "error": str(e)
                                         })
                
                # Store components
                self._parsers["config"] = config
                self._parsers["mapping"] = mapping
                self._parsers["support"] = support
                self._parsers["extractor"] = extractor
                
                # Update status based on parser availability
                has_parser = "tree_sitter" in self._parsers or "custom" in self._parsers
                
                if has_parser:
                    await global_health_monitor.update_component_status(
                        f"unified_parser_{self.language_id}",
                        ComponentStatus.HEALTHY,
                        details={
                            "tree_sitter_available": "tree_sitter" in self._parsers,
                            "custom_available": "custom" in self._parsers
                        }
                    )
                else:
                    await global_health_monitor.update_component_status(
                        f"unified_parser_{self.language_id}",
                        ComponentStatus.DEGRADED,
                        error=True,
                        details={"reason": "No suitable parser available"}
                    )
        except Exception as e:
            await log(f"Error initializing components: {e}", 
                     level="error",
                     context={
                         "component": "unified_parser",
                         "language_id": self.language_id,
                         "error_type": type(e).__name__,
                         "traceback": traceback.format_exc()
                     })
            
            await global_health_monitor.update_component_status(
                f"unified_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            
            raise ProcessingError(f"Failed to initialize components for {self.language_id}: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code using appropriate parser.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Optional[ParserResult]: The parsing result or None if parsing failed
        """
        try:
            async with AsyncErrorBoundary(f"unified_parse_{self.language_id}"):
                # Get appropriate parser
                parser = self._get_parser_for_source(source_code)
                if not parser:
                    raise ProcessingError(f"No suitable parser found for {self.language_id}")
                
                # Parse through async_runner
                parse_task = submit_async_task(parser.parse(source_code))
                result = await asyncio.wrap_future(parse_task)
                
                if not result:
                    raise ProcessingError(f"Parsing failed for {self.language_id}")
                
                # Extract features
                extractor = self._parsers.get("extractor")
                if extractor:
                    features = await extractor.extract_features(result.ast, source_code)
                    result.features = features
                
                await log(f"Source code parsed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error parsing source code: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_parse_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            return None
    
    def _get_parser_for_source(self, source_code: str) -> Optional[BaseParser]:
        """Get appropriate parser for source code."""
        # Try tree-sitter first if available
        if "tree_sitter" in self._parsers:
            return self._parsers["tree_sitter"]
        
        # Fallback to custom parser if available
        if "custom" in self._parsers:
            return self._parsers["custom"]
        
        return None
    
    @handle_async_errors(error_types=ProcessingError)
    async def validate(self, source_code: str) -> PatternValidationResult:
        """Validate source code using appropriate parser.
        
        Args:
            source_code: The source code to validate
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"unified_validate_{self.language_id}"):
                # Get appropriate parser
                parser = self._get_parser_for_source(source_code)
                if not parser:
                    return PatternValidationResult(
                        is_valid=False,
                        errors=["No suitable parser found"]
                    )
                
                # Validate through async_runner
                validate_task = submit_async_task(parser.validate(source_code))
                result = await asyncio.wrap_future(validate_task)
                
                await log(f"Source code validated for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error validating source code: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"unified_validate_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )

    @handle_async_errors(error_types=ProcessingError)
    async def parse_file_content(self, file_content: str, file_path: Optional[str] = None) -> ParserResult:
        """Parse file content.
        
        Args:
            file_content: Content to parse
            file_path: Optional file path for context
            
        Returns:
            ParserResult: Result of parsing
        """
        cache_key = f"parse_result:{self.language_id}:{hash(file_content)}"
        
        try:
            # Check cache first
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
            
            parser = await self._get_parser_for_language()
            if not parser:
                raise ProcessingError(f"No parser available for {self.language_id}")
            
            # Parse content
            result = await parser.parse_file_content(file_content, file_path)
            
            # Cache successful results
            if result.success:
                await self._cache_result(cache_key, result)
            
            return result
        except Exception as e:
            await log(f"Error parsing file content: {e}", level="error")
            result = ParserResult(
                success=False,
                file_type=self.file_type,
                parser_type=self.parser_type,
                language=self.language_id
            )
            result.errors.append(str(e))
            return result
    
    @handle_async_errors(error_types=ProcessingError)
    async def parse_incremental(self, file_content: str, old_tree=None, file_path: Optional[str] = None) -> ParserResult:
        """Parse file content with incremental parsing support.
        
        This method supports incremental parsing for tree-sitter parsers, which
        can significantly improve performance for repeated parsing of slightly
        modified files.
        
        Args:
            file_content: Content to parse
            old_tree: Optional previous tree for incremental parsing
            file_path: Optional file path for context
            
        Returns:
            ParserResult: Result of parsing
        """
        try:
            parser = await self._get_parser_for_language()
            if not parser:
                raise ProcessingError(f"No parser available for {self.language_id}")
            
            # Use incremental parsing for tree-sitter parsers
            if self.parser_type == ParserType.TREE_SITTER and hasattr(parser, 'parse_incremental'):
                result = await parser.parse_incremental(file_content, old_tree)
            else:
                # Fall back to regular parsing for non-tree-sitter parsers
                result = await parser.parse_file_content(file_content, file_path)
            
            return result
        except Exception as e:
            await log(f"Error in incremental parsing: {e}", level="error")
            result = ParserResult(
                success=False,
                file_type=self.file_type,
                parser_type=self.parser_type,
                language=self.language_id
            )
            result.errors.append(str(e))
            return result

    # Pattern Processor Integration Methods

    @handle_async_errors(error_types=ProcessingError)
    async def test_pattern(
        self,
        pattern_name: str,
        source_code: str,
        is_tree_sitter: bool = False
    ) -> Dict[str, Any]:
        """Test a pattern against source code.
        
        This method delegates to the appropriate component to test a pattern,
        using the most efficient approach available.
        
        Args:
            pattern_name: The name of the pattern to test
            source_code: The source code to test against
            is_tree_sitter: Whether to use tree-sitter for matching
            
        Returns:
            Dict[str, Any]: Test results including matches, performance metrics, and validation
            
        Raises:
            ProcessingError: If the pattern processor is not available or testing fails
        """
        try:
            async with AsyncErrorBoundary(f"unified_test_pattern_{self.language_id}", 
                                          error_types=(ProcessingError,),
                                          severity=ErrorSeverity.ERROR):
                
                # Update health status
                await global_health_monitor.update_component_status(
                    f"unified_parser_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "test_pattern",
                        "pattern_name": pattern_name
                    }
                )
                
                # First try parser-level testing if available
                parser = await self._get_parser_for_language()
                if parser and hasattr(parser, 'test_pattern'):
                    with monitor_operation("parser_test_pattern", f"parser_{self.language_id}"):
                        try:
                            result = await parser.test_pattern(pattern_name, source_code, is_tree_sitter)
                            if result:
                                return result
                        except Exception as e:
                            await log(f"Parser-level pattern testing failed, falling back to pattern processor: {e}", 
                                     level="warning")
                
                # Fall back to dedicated pattern processor
                from parsers.pattern_processor import get_pattern_processor
                
                pattern_processor = await get_pattern_processor(self.language_id)
                if not pattern_processor:
                    raise ProcessingError(f"Pattern processor not available for {self.language_id}")
                
                with monitor_operation("processor_test_pattern", f"pattern_processor_{self.language_id}"):
                    # Get result from pattern processor
                    result = await pattern_processor.test_pattern(pattern_name, source_code, is_tree_sitter)
                
                await log(f"Pattern {pattern_name} tested for {self.language_id}", 
                         level="debug",
                         context={
                             "component": "unified_parser",
                             "language_id": self.language_id,
                             "operation": "test_pattern",
                             "pattern_name": pattern_name,
                             "is_tree_sitter": is_tree_sitter
                         })
                
                return result
                
        except Exception as e:
            await log(f"Error testing pattern: {e}", 
                     level="error",
                     context={
                         "component": "unified_parser",
                         "language_id": self.language_id,
                         "operation": "test_pattern",
                         "pattern_name": pattern_name,
                         "error_type": type(e).__name__
                     })
            
            await ErrorAudit.record_error(
                e,
                f"unified_test_pattern_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "is_tree_sitter": is_tree_sitter
                }
            )
            
            return {
                "success": False,
                "errors": [str(e)],
                "pattern_name": pattern_name
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def validate_pattern_syntax(
        self,
        pattern_name: str
    ) -> Dict[str, Any]:
        """Validate the syntax of a pattern.
        
        This method delegates to the appropriate pattern processor
        to validate a pattern's syntax.
        
        Args:
            pattern_name: The name of the pattern to validate
            
        Returns:
            Dict[str, Any]: Validation results
            
        Raises:
            ProcessingError: If the pattern processor is not available or validation fails
        """
        from parsers.pattern_processor import get_pattern_processor
        
        try:
            # Get the pattern processor
            pattern_processor = await get_pattern_processor(self.language_id)
            if not pattern_processor:
                raise ProcessingError(f"Pattern processor not available for {self.language_id}")
            
            # Validate the pattern
            result = await pattern_processor.validate_pattern_syntax(pattern_name)
            
            return result
        except Exception as e:
            await log(f"Error validating pattern syntax: {e}", level="error")
            return {
                "valid": False,
                "errors": [str(e)],
                "pattern_name": pattern_name
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def export_patterns(
        self,
        format_type: str = "dict",
        pattern_type: str = "all"
    ) -> Union[Dict[str, Any], str]:
        """Export patterns in the requested format.
        
        This method delegates to the appropriate pattern processor
        to export patterns.
        
        Args:
            format_type: Format to export ("dict", "json", or "yaml")
            pattern_type: Type of patterns to export ("all", "tree_sitter", or "regex")
            
        Returns:
            Union[Dict[str, Any], str]: Exported patterns
            
        Raises:
            ProcessingError: If the pattern processor is not available or export fails
        """
        from parsers.pattern_processor import get_pattern_processor
        
        try:
            # Get the pattern processor
            pattern_processor = await get_pattern_processor(self.language_id)
            if not pattern_processor:
                raise ProcessingError(f"Pattern processor not available for {self.language_id}")
            
            # Export the patterns
            result = await pattern_processor.export_patterns(format_type, pattern_type)
            
            return result
        except Exception as e:
            await log(f"Error exporting patterns: {e}", level="error")
            return {} if format_type == "dict" else "{}" if format_type == "json" else ""
    
    # AI Pattern Processor Integration Methods
    
    @handle_async_errors(error_types=ProcessingError)
    async def analyze_with_ai(
        self,
        source_code: str,
        context: Optional[AIContext] = None
    ) -> AIProcessingResult:
        """Analyze code with AI assistance.
        
        This method delegates to the appropriate AI pattern processor
        to analyze code with AI capabilities, optimizing for tree-sitter
        when available.
        
        Args:
            source_code: The source code to analyze
            context: The AI processing context (optional)
            
        Returns:
            AIProcessingResult: The AI processing result
            
        Raises:
            ProcessingError: If the AI pattern processor is not available or analysis fails
        """
        from parsers.ai_pattern_processor import get_ai_pattern_processor
        
        try:
            async with AsyncErrorBoundary(f"analyze_with_ai_{self.language_id}",
                                          error_types=(ProcessingError,),
                                          severity=ErrorSeverity.ERROR):
                
                # Update health status
                await global_health_monitor.update_component_status(
                    f"unified_parser_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "analyze_with_ai",
                        "source_size": len(source_code)
                    }
                )
                
                # Check if result is cached
                cache_key = f"ai_analysis:{self.language_id}:{hash(source_code)}:{hash(str(context.__dict__) if context else '')}"
                cached_result = await self._get_cached_result(cache_key)
                if cached_result and isinstance(cached_result, AIProcessingResult):
                    return cached_result
                
                # Get the AI pattern processor
                ai_processor = await get_ai_pattern_processor(self.language_id)
                if not ai_processor:
                    raise ProcessingError(f"AI pattern processor not available for {self.language_id}")
                
                # Create context if not provided
                if not context:
                    context = AIContext(
                        language_id=self.language_id,
                        file_type=self.file_type,
                        interaction_type="analysis"
                    )
                
                # Check if tree-sitter is available and supported
                support = self._parsers.get("support")
                has_tree_sitter = (
                    support and 
                    support.level.supports_tree_sitter and 
                    "tree_sitter" in self._parsers and 
                    self._parsers["tree_sitter"] is not None
                )
                
                with monitor_operation("ai_analysis", f"ai_processor_{self.language_id}"):
                    # Use tree-sitter for analysis if available
                    if has_tree_sitter and hasattr(ai_processor, "analyze_with_tree_sitter"):
                        await log(f"Using tree-sitter for AI analysis of {self.language_id}", 
                                 level="debug",
                                 context={
                                     "component": "unified_parser",
                                     "language_id": self.language_id,
                                     "operation": "analyze_with_ai",
                                     "parser_type": "tree_sitter"
                                 })
                        
                        # Enhance context with tree-sitter parser
                        enhanced_context = AIContext(
                            **context.__dict__,
                            parser_type=ParserType.TREE_SITTER,
                            tree_sitter_available=True,
                            tree_sitter_parser=self._parsers["tree_sitter"]
                        )
                        
                        result = await ai_processor.analyze_with_tree_sitter(source_code, enhanced_context)
                    else:
                        # Fall back to generic AI processing
                        await log(f"Using standard AI processing for {self.language_id}", 
                                 level="debug",
                                 context={
                                     "component": "unified_parser",
                                     "language_id": self.language_id,
                                     "operation": "analyze_with_ai",
                                     "parser_type": "standard",
                                     "tree_sitter_available": has_tree_sitter
                                 })
                        
                        result = await ai_processor.process_with_ai(source_code, context)
                        
                        # Convert result to AIProcessingResult if needed
                        if isinstance(result, PatternValidationResult):
                            result = AIProcessingResult(
                                success=result.is_valid,
                                errors=result.errors,
                                processing_time=result.validation_time
                            )
                
                # Cache successful results
                if result and result.success:
                    await self._cache_result(cache_key, result)
                
                await log(f"AI analysis completed for {self.language_id}", 
                         level="info",
                         context={
                             "component": "unified_parser",
                             "language_id": self.language_id,
                             "operation": "analyze_with_ai",
                             "success": result.success if result else False,
                             "tree_sitter_used": has_tree_sitter
                         })
                
                return result
                
        except Exception as e:
            await log(f"Error analyzing with AI: {e}", 
                     level="error",
                     context={
                         "component": "unified_parser",
                         "language_id": self.language_id,
                         "operation": "analyze_with_ai",
                         "error_type": type(e).__name__,
                         "traceback": traceback.format_exc()
                     })
            
            await ErrorAudit.record_error(
                e,
                f"analyze_with_ai_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.ERROR,
                context={
                    "language_id": self.language_id,
                    "source_size": len(source_code)
                }
            )
            
            return AIProcessingResult(
                success=False,
                errors=[str(e)]
            )
    
    @handle_async_errors(error_types=ProcessingError)
    async def learn_patterns_from_code(
        self,
        source_code: str,
        context: Optional[AIContext] = None
    ) -> List[Dict[str, Any]]:
        """Learn patterns from source code using AI.
        
        This method delegates to the appropriate AI pattern processor
        to learn patterns from code.
        
        Args:
            source_code: The source code to learn from
            context: The AI learning context (optional)
            
        Returns:
            List[Dict[str, Any]]: The learned patterns
            
        Raises:
            ProcessingError: If the AI pattern processor is not available or learning fails
        """
        from parsers.ai_pattern_processor import get_ai_pattern_processor
        
        try:
            # Get the AI pattern processor
            ai_processor = await get_ai_pattern_processor(self.language_id)
            if not ai_processor:
                raise ProcessingError(f"AI pattern processor not available for {self.language_id}")
            
            # Create context if not provided
            if not context:
                context = AIContext(
                    language_id=self.language_id,
                    file_type=self.file_type,
                    interaction_type="learning"
                )
            
            # Learn patterns
            learned_patterns = await ai_processor.learn_from_code(source_code, context)
            
            return learned_patterns
        except Exception as e:
            await log(f"Error learning patterns from code: {e}", level="error")
            raise ProcessingError(f"Failed to learn patterns from code: {e}")

    async def _get_parser_for_language(self) -> Optional[BaseParserInterface]:
        """Get appropriate parser for the current language.
        
        This method retrieves the appropriate parser for the language,
        with tree-sitter parsers taking precedence over custom parsers.
        
        Returns:
            Optional[BaseParserInterface]: The parser or None if no suitable parser is found
        """
        # Check if we're already initialized
        if not self._initialized:
            await self.ensure_initialized()
        
        # Try tree-sitter first if available and this is a tree-sitter parser type
        if self.parser_type == ParserType.TREE_SITTER and "tree_sitter" in self._parsers:
            return self._parsers["tree_sitter"]
        
        # Try custom parser if available and this is a custom parser type
        if self.parser_type == ParserType.CUSTOM and "custom" in self._parsers:
            return self._parsers["custom"]
        
        # Fallback - use whatever parser is available
        for key, parser in self._parsers.items():
            # Skip non-parser components
            if key in ["config", "mapping", "support", "extractor"]:
                continue
                
            # Use any parser that implements the interface
            if isinstance(parser, BaseParserInterface):
                return parser
        
        return None

    async def _get_cached_result(self, cache_key: str) -> Optional[ParserResult]:
        """Get cached parsing result.
        
        This method checks both the AST cache and the request cache for cached results.
        
        Args:
            cache_key: The cache key to check
            
        Returns:
            Optional[ParserResult]: The cached result or None if not found
        """
        try:
            # First check request cache
            request_cache = get_current_request_cache()
            if request_cache:
                cached_value = request_cache.get(cache_key)
                if cached_value:
                    await log(f"Request cache hit for {cache_key}", 
                             level="debug",
                             context={
                                 "component": "unified_parser",
                                 "language_id": self.language_id,
                                 "cache_type": "request"
                             })
                    return ParserResult(**cached_value) if isinstance(cached_value, dict) else cached_value
            
            # Then check AST cache
            if self._ast_cache:
                cached_value = await self._ast_cache.get(cache_key)
                if cached_value:
                    # Record cache hit with analytics
                    await get_cache_analytics().record_hit(f"{self.language_id}_ast", cache_key)
                    
                    await log(f"AST cache hit for {cache_key}", 
                             level="debug",
                             context={
                                 "component": "unified_parser",
                                 "language_id": self.language_id,
                                 "cache_type": "ast"
                             })
                    
                    result = ParserResult(**cached_value) if isinstance(cached_value, dict) else cached_value
                    
                    # Store in request cache for future use
                    if request_cache:
                        request_cache.set(cache_key, cached_value)
                    
                    return result
            
            # Record cache miss with analytics
            await get_cache_analytics().record_miss(f"{self.language_id}_ast", cache_key)
            
            return None
        except Exception as e:
            await log(f"Error retrieving from cache: {e}", 
                     level="warning",
                     context={
                         "component": "unified_parser",
                         "language_id": self.language_id,
                         "cache_key": cache_key,
                         "error_type": type(e).__name__
                     })
            return None

    async def _cache_result(self, cache_key: str, result: ParserResult) -> None:
        """Cache parsing result.
        
        This method stores the result in both the AST cache and the request cache.
        
        Args:
            cache_key: The cache key to use
            result: The result to cache
        """
        try:
            # Only cache successful results
            if not result or not result.success:
                return
            
            # Store in request cache
            request_cache = get_current_request_cache()
            if request_cache:
                result_dict = result.__dict__ if hasattr(result, '__dict__') else result
                request_cache.set(cache_key, result_dict)
            
            # Store in AST cache
            if self._ast_cache:
                result_dict = result.__dict__ if hasattr(result, '__dict__') else result
                await self._ast_cache.set(cache_key, result_dict)
                
                # Record cache set with analytics
                await get_cache_analytics().record_set(f"{self.language_id}_ast", cache_key)
                
                await log(f"Result cached with key {cache_key}", 
                         level="debug",
                         context={
                             "component": "unified_parser",
                             "language_id": self.language_id,
                             "cache_types": ["ast", "request"] if request_cache else ["ast"]
                         })
        except Exception as e:
            await log(f"Error saving to cache: {e}", 
                     level="warning",
                     context={
                         "component": "unified_parser",
                         "language_id": self.language_id,
                         "cache_key": cache_key,
                         "error_type": type(e).__name__
                     })

# Global instance cache
_parser_instances: Dict[str, UnifiedParser] = {}

async def get_unified_parser(
    language_id: str,
    file_type: FileType = FileType.CODE,
    parser_type: ParserType = ParserType.TREE_SITTER
) -> Optional[UnifiedParser]:
    """Get a unified parser instance.
    
    This factory method creates or retrieves a UnifiedParser instance
    for the specified language, file type, and parser type.
    
    Args:
        language_id: The language to get parser for
        file_type: The type of files to parse (default: CODE)
        parser_type: The type of parser to use (default: TREE_SITTER)
        
    Returns:
        Optional[UnifiedParser]: The parser instance or None if initialization fails
        
    Raises:
        ProcessingError: If parser initialization fails
    """
    try:
        async with AsyncErrorBoundary(f"get_unified_parser_{language_id}",
                                     error_types=(Exception,),
                                     severity=ErrorSeverity.ERROR):
            
            # Generate cache key
            key = f"{language_id}:{file_type.value}:{parser_type.value}"
            
            # Check if parser instance already exists
            if key in _parser_instances:
                instance = _parser_instances[key]
                # Check if instance is initialized and healthy
                if instance._initialized and await global_health_monitor.is_component_healthy(f"unified_parser_{language_id}"):
                    return instance
            
            await log(f"Creating new UnifiedParser instance for {language_id}", 
                     level="info",
                     context={
                         "component": "unified_parser_factory",
                         "language_id": language_id,
                         "file_type": file_type.value,
                         "parser_type": parser_type.value
                     })
            
            # Create parser instance
            parser = UnifiedParser(language_id, file_type, parser_type)
            
            # Initialize through async_runner
            init_task = submit_async_task(parser.initialize())
            initialized = await asyncio.wrap_future(init_task)
            
            if initialized:
                _parser_instances[key] = parser
                
                await log(f"UnifiedParser instance created and initialized for {language_id}", 
                         level="info",
                         context={
                             "component": "unified_parser_factory",
                             "language_id": language_id,
                             "file_type": file_type.value,
                             "parser_type": parser_type.value,
                             "cache_key": key
                         })
                
                return parser
            else:
                await log(f"Failed to initialize UnifiedParser for {language_id}", 
                         level="error",
                         context={
                             "component": "unified_parser_factory",
                             "language_id": language_id,
                             "file_type": file_type.value,
                             "parser_type": parser_type.value
                         })
                
                # Record error
                await ErrorAudit.record_error(
                    ProcessingError(f"Failed to initialize UnifiedParser for {language_id}"),
                    f"unified_parser_init_{language_id}",
                    ProcessingError,
                    severity=ErrorSeverity.ERROR,
                    context={
                        "language_id": language_id,
                        "file_type": file_type.value,
                        "parser_type": parser_type.value
                    }
                )
                
                return None
    except Exception as e:
        await log(f"Error getting unified parser for {language_id}: {e}", 
                 level="error",
                 context={
                     "component": "unified_parser_factory",
                     "language_id": language_id,
                     "file_type": file_type.value,
                     "parser_type": parser_type.value,
                     "error_type": type(e).__name__,
                     "traceback": traceback.format_exc()
                 })
        
        # Record error
        await ErrorAudit.record_error(
            e,
            f"get_unified_parser_{language_id}",
            ProcessingError,
            severity=ErrorSeverity.ERROR,
            context={
                "language_id": language_id,
                "file_type": file_type.value,
                "parser_type": parser_type.value
            }
        )
        
        return None

# Export public interfaces
__all__ = [
    'UnifiedParser',
    'get_unified_parser'
] 