"""
Custom EditorConfig parser.

This module implements a lightweight parser for EditorConfig files.
It extracts section headers (e.g. [*] or [*.py]) and
key-value property lines beneath each section.
"""

from .base_imports import (
    # Base classes
    BaseParser,
    CustomParserMixin,
    
    # Types
    FileType,
    ParserType,
    PatternType,
    PatternCategory,
    FeatureCategory,
    
    # AI related
    AICapability,
    AIContext,
    AIProcessingResult,
    AIConfidenceMetrics,
    AIPatternProcessor,
    
    # Pattern related
    PatternProcessor,
    AdaptivePattern,
    ResilientPattern,
    
    # Documentation
    Documentation,
    ComplexityMetrics,
    
    # Node types
    EditorconfigNodeDict,
    
    # Utils
    ComponentStatus,
    monitor_operation,
    handle_errors,
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ParsingError,
    ErrorSeverity,
    global_health_monitor,
    register_shutdown_handler,
    log,
    UnifiedCache,
    cache_coordinator,
    get_cache_analytics,
    
    # Python types
    Dict,
    List,
    Any,
    Optional,
    Set,
    
    # Python modules
    time,
    asyncio
)
import configparser
import re
from parsers.query_patterns.editorconfig import (
    ENHANCED_PATTERNS,
    EditorconfigPatternContext,
    pattern_learner,
    initialize_caches,
    PATTERN_METRICS
)


class EditorconfigParser(BaseParser, CustomParserMixin):
    """Parser for EditorConfig files."""
    
    def __init__(self, language_id: str = "editorconfig", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CONFIG, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
        self._pattern_metrics = PATTERN_METRICS
        self._pattern_learner = pattern_learner
        register_shutdown_handler(self.cleanup)
        
        # Compile regex patterns for parsing
        self.section_pattern = re.compile(r'^\s*\[(.*)\]\s*$')
        self.property_pattern = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')
        self.comment_pattern = re.compile(r'^\s*[#;](.*)$')
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("EditorConfig parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await initialize_caches()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    # Initialize pattern learner
                    await self._pattern_learner.initialize()
                    
                    self._initialized = True
                    log("EditorConfig parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing EditorConfig parser: {e}", level="error")
                raise
        return True

    async def cleanup(self) -> None:
        """Clean up parser resources."""
        try:
            # Clean up base resources
            await self._cleanup_cache()
            
            # Clean up AI processor
            if self._ai_processor:
                await self._ai_processor.cleanup()
                self._ai_processor = None
            
            # Clean up pattern processor
            if self._pattern_processor:
                await self._pattern_processor.cleanup()
                self._pattern_processor = None
            
            # Cancel pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("EditorConfig parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up EditorConfig parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> EditorconfigNodeDict:
        """Create a standardized EditorConfig AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "properties": kwargs.get("properties", []),
            "sections": kwargs.get("sections", []),
            "metadata": kwargs.get("metadata", {}),
            "relationships": kwargs.get("relationships", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse EditorConfig content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="EditorConfig parsing",
            error_types=(ParsingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                
                # Create context for pattern matching
                context = EditorconfigPatternContext()
                
                # Parse with enhanced patterns
                ast = await self._parse_with_enhanced_patterns(source_code, context)
                
                # Store result in cache
                await self._store_parse_result(source_code, ast)
                
                return ast
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing EditorConfig content: {e}", level="error")
                return self._create_node(
                    "document",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    async def _parse_with_enhanced_patterns(
        self,
        source_code: str,
        context: EditorconfigPatternContext
    ) -> Dict[str, Any]:
        """Parse content using enhanced patterns."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "document",
            [0, 0],
            [len(lines) - 1, len(lines[-1]) if lines else 0]
        )

        try:
            # Process each pattern category
            for category in PatternCategory:
                if category in ENHANCED_PATTERNS:
                    category_patterns = ENHANCED_PATTERNS[category]
                    for pattern_name, pattern in category_patterns.items():
                        try:
                            matches = await pattern.matches(source_code, context)
                            for match in matches:
                                node = self._create_node(
                                    match["type"],
                                    [match.get("line_number", 0) - 1, 0],
                                    [match.get("line_number", 0) - 1, len(match.get("content", ""))],
                                    content=match.get("content", ""),
                                    metadata=match,
                                    relationships=match.get("relationships", [])
                                )
                                ast["children"].append(node)
                                
                                # Update context
                                self._update_context(context, match)
                                
                        except Exception as e:
                            log(f"Error processing pattern {pattern_name}: {e}", level="warning")
                            continue
            
            return ast.__dict__
            
        except Exception as e:
            log(f"Error in enhanced pattern parsing: {e}", level="error")
            return ast.__dict__

    def _update_context(self, context: EditorconfigPatternContext, match: Dict[str, Any]) -> None:
        """Update pattern context based on match."""
        match_type = match.get("type", "")
        
        if match_type == "section":
            context.section_names.add(match.get("glob", ""))
            context.has_sections = True
        elif match_type == "property":
            context.property_names.add(match.get("key", ""))
            context.has_properties = True
        elif match_type == "glob_pattern":
            context.glob_patterns.add(match.get("pattern", ""))
        elif match_type == "root":
            context.has_root = True
        elif match_type == "comment":
            context.has_comments = True

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from EditorConfig files for repository learning."""
        if not self._initialized:
            await self.initialize()

        patterns = []
        context = EditorconfigPatternContext()
        
        async with AsyncErrorBoundary(
            operation_name="EditorConfig pattern extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Update health status
                await global_health_monitor.update_component_status(
                    "editorconfig_pattern_processor",
                    ComponentStatus.PROCESSING,
                    details={"operation": "pattern_extraction"}
                )
                
                # Process with enhanced patterns
                with monitor_operation("extract_patterns", "editorconfig_processor"):
                    for category in PatternCategory:
                        if category in ENHANCED_PATTERNS:
                            category_patterns = ENHANCED_PATTERNS[category]
                            for pattern_name, pattern in category_patterns.items():
                                try:
                                    matches = await pattern.matches(source_code, context)
                                    for match in matches:
                                        patterns.append({
                                            "name": pattern_name,
                                            "category": category.value,
                                            "content": match.get("text", ""),
                                            "metadata": match,
                                            "confidence": pattern.confidence,
                                            "relationships": match.get("relationships", {})
                                        })
                                        
                                        # Update metrics
                                        if pattern_name in self._pattern_metrics:
                                            self._pattern_metrics[pattern_name].update(
                                                True,
                                                time.time(),
                                                context.get_context_key(),
                                                self.parser_type
                                            )
                                        
                                        # Update context
                                        self._update_context(context, match)
                                        
                                except Exception as e:
                                    log(f"Error processing pattern {pattern_name}: {e}", level="error")
                                    if pattern_name in self._pattern_metrics:
                                        self._pattern_metrics[pattern_name].update(
                                            False,
                                            time.time(),
                                            context.get_context_key(),
                                            self.parser_type
                                        )
                                    continue
                
                # Update final status
                await global_health_monitor.update_component_status(
                    "editorconfig_pattern_processor",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "pattern_extraction_complete",
                        "patterns_found": len(patterns),
                        "context": context.__dict__
                    }
                )
                    
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error extracting EditorConfig patterns: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "editorconfig_pattern_processor",
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={"error": str(e)}
                )
                
        return patterns

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process EditorConfig with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("EditorConfig AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse EditorConfig"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Create pattern context
                pattern_context = EditorconfigPatternContext()
                
                # Process with enhanced patterns first
                enhanced_matches = await self._process_with_enhanced_patterns(
                    source_code,
                    pattern_context
                )
                if enhanced_matches:
                    results.matches = enhanced_matches
                
                # Process with AI pattern processor
                if self._ai_processor:
                    ai_results = await self._ai_processor.process_with_ai(source_code, context)
                    if ai_results.success:
                        results.ai_insights.update(ai_results.ai_insights)
                        results.learned_patterns.extend(ai_results.learned_patterns)
                
                # Extract features with AI assistance
                features = await self._extract_features_with_ai(ast, source_code, context)
                results.context_info.update(features)
                
                # Calculate confidence metrics
                results.confidence_metrics = await self._calculate_confidence_metrics(
                    ast,
                    features,
                    enhanced_matches,
                    context
                )
                
                return results
            except Exception as e:
                log(f"Error in EditorConfig AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_enhanced_patterns(
        self,
        source_code: str,
        context: EditorconfigPatternContext
    ) -> List[Dict[str, Any]]:
        """Process source code with enhanced patterns."""
        matches = []
        
        for category in PatternCategory:
            if category in ENHANCED_PATTERNS:
                category_patterns = ENHANCED_PATTERNS[category]
                for pattern_name, pattern in category_patterns.items():
                    try:
                        pattern_matches = await pattern.matches(source_code, context)
                        matches.extend(pattern_matches)
                    except Exception as e:
                        log(f"Error in enhanced pattern processing: {e}", level="error")
                        continue
        
        return matches

    async def _extract_features_with_ai(
        self,
        ast: Dict[str, Any],
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """Extract features with AI assistance."""
        features = {}
        
        # Process each feature category
        for category in FeatureCategory:
            category_features = await self._extract_category_features(
                category,
                ast,
                source_code
            )
            if category_features:
                features[category] = category_features
                
                # Apply AI enhancement if available
                if self._ai_processor:
                    enhanced = await self._ai_processor.enhance_features(
                        category_features,
                        category,
                        context
                    )
                    features[f"{category}_enhanced"] = enhanced
        
        return features

    async def _calculate_confidence_metrics(
        self,
        ast: Dict[str, Any],
        features: Dict[str, Any],
        pattern_matches: List[Dict[str, Any]],
        context: AIContext
    ) -> AIConfidenceMetrics:
        """Calculate confidence metrics for AI processing."""
        metrics = AIConfidenceMetrics()
        
        # Calculate pattern match confidence
        if pattern_matches:
            pattern_confidences = {}
            for match in pattern_matches:
                pattern_name = match.get('pattern_name', 'unknown')
                confidence = match.get('confidence', 0.5)
                pattern_confidences[pattern_name] = confidence
            metrics.pattern_matches = pattern_confidences
            metrics.overall_confidence = sum(pattern_confidences.values()) / len(pattern_confidences)
        
        # Calculate context relevance
        if context.metadata:
            metrics.context_relevance = self._calculate_context_relevance(
                ast,
                context
            )
        
        # Calculate semantic similarity
        metrics.semantic_similarity = self._calculate_semantic_similarity(
            features
        )
        
        # Calculate configuration quality
        if 'syntax' in features:
            metrics.code_quality = self._calculate_config_quality(
                features['syntax']
            )
        
        # Calculate learning progress
        if self._pattern_learner:
            metrics.learning_progress = await self._pattern_learner.get_learning_progress()
        
        return metrics

    def _calculate_context_relevance(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> float:
        """Calculate relevance of context to the configuration."""
        relevance = 0.0
        total_weights = 0
        
        # Check file type relevance
        if context.file_type == FileType.CONFIG:
            relevance += 1.0
            total_weights += 1
        
        # Check language relevance
        if context.language_id == "editorconfig":
            relevance += 1.0
            total_weights += 1
        
        # Check content relevance
        if ast.get('metadata'):
            metadata_match = len(set(ast['metadata'].keys()) & 
                               set(context.metadata.keys()))
            if metadata_match:
                relevance += metadata_match / len(context.metadata)
                total_weights += 1
        
        return relevance / total_weights if total_weights > 0 else 0.0

    def _calculate_semantic_similarity(
        self,
        features: Dict[str, Any]
    ) -> float:
        """Calculate semantic similarity of configuration features."""
        similarity = 0.0
        total_weights = 0
        
        # Check structure similarity
        if 'structure' in features:
            structure = features['structure']
            if structure.get('sections'):
                similarity += len(structure['sections']) / 10  # Normalize to 0-1
                total_weights += 1
            if structure.get('properties'):
                similarity += len(structure['properties']) / 20  # Normalize to 0-1
                total_weights += 1
        
        # Check semantic features
        if 'semantics' in features:
            semantics = features['semantics']
            if semantics.get('glob_patterns'):
                similarity += len(semantics['glob_patterns']) / 5  # Normalize to 0-1
                total_weights += 1
        
        return similarity / total_weights if total_weights > 0 else 0.0

    def _calculate_config_quality(
        self,
        syntax: Dict[str, Any]
    ) -> float:
        """Calculate configuration quality score."""
        quality = 0.0
        total_weights = 0
        
        # Check section organization
        if syntax.get('sections'):
            section_quality = len(syntax['sections']) / 10  # Normalize
            quality += min(1.0, section_quality)
            total_weights += 1
        
        # Check property organization
        if syntax.get('properties'):
            prop_quality = len(syntax['properties']) / 20  # Normalize
            quality += min(1.0, prop_quality)
            total_weights += 1
        
        # Check glob pattern quality
        if syntax.get('glob_patterns'):
            glob_quality = len(syntax['glob_patterns']) / 5  # Normalize
            quality += min(1.0, glob_quality)
            total_weights += 1
        
        return quality / total_weights if total_weights > 0 else 0.0