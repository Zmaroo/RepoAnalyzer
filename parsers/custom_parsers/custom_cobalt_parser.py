"""
Custom parser for the Cobalt programming language with enhanced pattern support.
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
    CobaltNodeDict,
    
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
import re
from parsers.query_patterns.cobalt import (
    ENHANCED_PATTERNS,
    CobaltPatternContext,
    pattern_learner,
    initialize_caches,
    PATTERN_METRICS
)

class CobaltParser(BaseParser, CustomParserMixin):
    """Parser for the Cobalt programming language."""
    
    def __init__(self, language_id: str = "cobalt", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
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
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("Cobalt parser initialization"):
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
                    log("Cobalt parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing Cobalt parser: {e}", level="error")
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
            log("Cobalt parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up Cobalt parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> CobaltNodeDict:
        """Create a standardized Cobalt AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        
        # Determine pattern category based on node type
        category = PatternCategory.SYNTAX
        if node_type in ["docstring", "comment"]:
            category = PatternCategory.DOCUMENTATION
        elif node_type in ["import", "use"]:
            category = PatternCategory.DEPENDENCIES
        
        # Determine pattern type
        pattern_type = PatternType.CODE_STRUCTURE
        if node_type in ["class", "function", "variable"]:
            pattern_type = PatternType.CODE_NAMING
        elif node_type in ["try", "catch", "throw"]:
            pattern_type = PatternType.ERROR_HANDLING
        
        return {
            **node_dict,
            "category": category,
            "pattern_type": pattern_type,
            "name": kwargs.get("name"),
            "parameters": kwargs.get("parameters", []),
            "return_type": kwargs.get("return_type"),
            "parent_class": kwargs.get("parent_class"),
            "namespace": kwargs.get("namespace"),
            "type_parameters": kwargs.get("type_parameters", []),
            "is_function": node_type == "function",
            "is_class": node_type == "class",
            "is_namespace": node_type == "namespace",
            "is_type_def": node_type == "type_definition",
            "is_enum": node_type == "enum",
            "visibility": kwargs.get("visibility"),
            "decorators": kwargs.get("decorators", []),
            "doc_comments": kwargs.get("doc_comments", []),
            "feature_category": FeatureCategory.SYNTAX,
            "pattern_relationships": kwargs.get("pattern_relationships", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Cobalt content into AST structure."""
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(
            operation_name="Cobalt parsing",
            error_types=(ParsingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                
                # Create context for pattern matching
                context = CobaltPatternContext()
                
                # Parse with enhanced patterns
                ast = await self._parse_with_enhanced_patterns(source_code, context)
                
                # Store result in cache
                await self._store_parse_result(source_code, ast)
                
                return ast
                
            except (ValueError, KeyError, TypeError, StopIteration) as e:
                log(f"Error parsing Cobalt content: {e}", level="error")
                return self._create_node(
                    "module",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    async def _parse_with_enhanced_patterns(
        self,
        source_code: str,
        context: CobaltPatternContext
    ) -> Dict[str, Any]:
        """Parse content using enhanced patterns."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "module",
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

    def _update_context(self, context: CobaltPatternContext, match: Dict[str, Any]) -> None:
        """Update pattern context based on match."""
        match_type = match.get("type", "")
        
        if match_type == "function":
            context.function_names.add(match.get("name", ""))
            context.has_functions = True
        elif match_type == "class":
            context.class_names.add(match.get("name", ""))
            context.has_classes = True
        elif match_type == "namespace":
            context.namespace_names.add(match.get("name", ""))
            context.has_namespaces = True
        elif match_type == "type":
            context.type_names.add(match.get("name", ""))
            context.has_types = True
        elif match_type in ["try_catch", "throw"]:
            context.has_error_handling = True

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract code patterns from Cobalt files for repository learning."""
        if not self._initialized:
            await self.initialize()

        patterns = []
        context = CobaltPatternContext()
        
        async with AsyncErrorBoundary(
            operation_name="Cobalt pattern extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Update health status
                await global_health_monitor.update_component_status(
                    "cobalt_pattern_processor",
                    ComponentStatus.PROCESSING,
                    details={"operation": "pattern_extraction"}
                )
                
                # Process with enhanced patterns
                with monitor_operation("extract_patterns", "cobalt_processor"):
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
                    "cobalt_pattern_processor",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "pattern_extraction_complete",
                        "patterns_found": len(patterns),
                        "context": context.__dict__
                    }
                )
                    
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error extracting Cobalt patterns: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "cobalt_pattern_processor",
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
        """Process Cobalt code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("Cobalt AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse Cobalt code"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Create pattern context
                pattern_context = CobaltPatternContext()
                
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
                log(f"Error in Cobalt AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_enhanced_patterns(
        self,
        source_code: str,
        context: CobaltPatternContext
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
        
        # Calculate code quality
        if 'syntax' in features:
            metrics.code_quality = self._calculate_code_quality(
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
        """Calculate relevance of context to the code."""
        relevance = 0.0
        total_weights = 0
        
        # Check file type relevance
        if context.file_type == FileType.CODE:
            relevance += 1.0
            total_weights += 1
        
        # Check language relevance
        if context.language_id == "cobalt":
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
        """Calculate semantic similarity of code features."""
        similarity = 0.0
        total_weights = 0
        
        # Check structure similarity
        if 'structure' in features:
            structure = features['structure']
            if structure.get('functions'):
                similarity += len(structure['functions']) / 10  # Normalize to 0-1
                total_weights += 1
            if structure.get('classes'):
                similarity += len(structure['classes']) / 5  # Normalize to 0-1
                total_weights += 1
        
        # Check semantic features
        if 'semantics' in features:
            semantics = features['semantics']
            if semantics.get('types'):
                similarity += len(semantics['types']) / 10  # Normalize to 0-1
                total_weights += 1
        
        return similarity / total_weights if total_weights > 0 else 0.0

    def _calculate_code_quality(
        self,
        syntax: Dict[str, Any]
    ) -> float:
        """Calculate code quality score."""
        quality = 0.0
        total_weights = 0
        
        # Check function organization
        if syntax.get('functions'):
            func_quality = len(syntax['functions']) / 20  # Normalize
            quality += min(1.0, func_quality)
            total_weights += 1
        
        # Check class organization
        if syntax.get('classes'):
            class_quality = len(syntax['classes']) / 10  # Normalize
            quality += min(1.0, class_quality)
            total_weights += 1
        
        # Check error handling
        if syntax.get('error_handling'):
            error_quality = len(syntax['error_handling']) / 5  # Normalize
            quality += min(1.0, error_quality)
            total_weights += 1
        
        return quality / total_weights if total_weights > 0 else 0.0 