"""Custom parser for INI files with enhanced pattern support."""

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
    IniNodeDict,
    
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
    Counter,
    
    # Python modules
    time,
    asyncio
)
import configparser
import re
from parsers.query_patterns.ini import (
    ENHANCED_PATTERNS,
    INIPatternContext,
    pattern_learner,
    initialize_caches,
    PATTERN_METRICS
)


class IniParser(BaseParser, CustomParserMixin):
    """Parser for INI files."""
    
    def __init__(self, language_id: str = "ini", file_type: Optional[FileType] = None):
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
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("INI parser initialization"):
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
                    log("INI parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing INI parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> IniNodeDict:
        """Create a standardized INI AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "section": kwargs.get("section"),
            "properties": kwargs.get("properties", []),
            "metadata": kwargs.get("metadata", {}),
            "relationships": kwargs.get("relationships", [])
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse INI content into AST structure."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name="INI parsing",
            error_types=(ParsingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Check cache first
                cached_result = await self._check_parse_cache(source_code)
                if cached_result:
                    return cached_result
                
                # Create context for pattern matching
                context = INIPatternContext()
                
                # Parse with enhanced patterns
                ast = await self._parse_with_enhanced_patterns(source_code, context)
                
                # Store result in cache
                await self._store_parse_result(source_code, ast)
                
                return ast
                
            except (ValueError, KeyError, TypeError) as e:
                log(f"Error parsing INI content: {e}", level="error")
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
        context: INIPatternContext
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

    def _update_context(self, context: INIPatternContext, match: Dict[str, Any]) -> None:
        """Update pattern context based on match."""
        match_type = match.get("type", "")
        
        if match_type == "section":
            context.section_names.add(match.get("name", ""))
            context.has_sections = True
        elif match_type == "property":
            context.property_names.add(match.get("key", ""))
            context.has_properties = True
        elif match_type == "include":
            context.has_includes = True
        elif match_type == "reference":
            context.has_references = True
        elif match_type == "comment":
            context.has_comments = True

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract patterns from INI files for repository learning."""
        if not self._initialized:
            await self.initialize()

        patterns = []
        context = INIPatternContext()
        
        async with AsyncErrorBoundary(
            operation_name="INI pattern extraction",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Update health status
                await global_health_monitor.update_component_status(
                    "ini_pattern_processor",
                    ComponentStatus.PROCESSING,
                    details={"operation": "pattern_extraction"}
                )
                
                # Process with enhanced patterns
                with monitor_operation("extract_patterns", "ini_processor"):
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
                    "ini_pattern_processor",
                    ComponentStatus.HEALTHY,
                    details={
                        "operation": "pattern_extraction_complete",
                        "patterns_found": len(patterns),
                        "context": context.__dict__
                    }
                )
                    
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error extracting INI patterns: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "ini_pattern_processor",
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
        """Process INI with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("INI AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse INI file"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Create pattern context
                pattern_context = INIPatternContext()
                
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
                log(f"Error in INI AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_enhanced_patterns(
        self,
        source_code: str,
        context: INIPatternContext
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
        if context.language_id == "ini":
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
            if semantics.get('references'):
                similarity += len(semantics['references']) / 5  # Normalize to 0-1
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
        
        # Check reference quality
        if syntax.get('references'):
            ref_quality = len(syntax['references']) / 5  # Normalize
            quality += min(1.0, ref_quality)
            total_weights += 1
        
        return quality / total_weights if total_weights > 0 else 0.0

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
            log("INI parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up INI parser: {e}", level="error")

    def _extract_section_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract section patterns from the AST."""
        sections = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'section':
                properties = []
                
                # Extract properties from this section
                for child in node.get('children', []):
                    if isinstance(child, dict) and child.get('type') == 'option':
                        properties.append({
                            'key': child.get('key', ''),
                            'value': child.get('value', '')
                        })
                
                section_name = node.get('name', '')
                if section_name:
                    sections.append({
                        'name': section_name,
                        'content': f"[{section_name}]\n" + "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                        'options': properties
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return sections
        
    def _extract_option_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common property patterns from the AST."""
        property_categories = {}
        
        def collect_properties(node, categories=None):
            if categories is None:
                categories = {}
                
            if isinstance(node, dict):
                # Check properties directly
                if node.get('type') == 'option':
                    key = node.get('key', '').lower()
                    value = node.get('value', '')
                    
                    # Categorize properties
                    if any(term in key for term in ['host', 'server', 'url', 'endpoint']):
                        category = 'connection'
                    elif any(term in key for term in ['user', 'password', 'auth', 'token', 'key', 'secret']):
                        category = 'authentication'
                    elif any(term in key for term in ['log', 'debug', 'verbose', 'trace']):
                        category = 'logging'
                    elif any(term in key for term in ['dir', 'path', 'file', 'folder']):
                        category = 'filesystem'
                    elif any(term in key for term in ['port', 'timeout', 'retry', 'max', 'min']):
                        category = 'connection_params'
                    elif any(term in key for term in ['enable', 'disable', 'toggle', 'feature']):
                        category = 'feature_flags'
                    else:
                        category = 'other'
                        
                    if category not in categories:
                        categories[category] = []
                        
                    categories[category].append({
                        'key': key,
                        'value': value
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_properties(child, categories)
                    
            return categories
            
        # Collect properties by category
        property_categories = collect_properties(ast)
        
        # Create patterns for each category
        patterns = []
        for category, properties in property_categories.items():
            if properties:  # Only include non-empty categories
                patterns.append({
                    'category': category,
                    'content': "\n".join(f"{prop['key']} = {prop['value']}" for prop in properties[:3]),
                    'value_type': category,
                    'examples': properties[:3]
                })
                
        return patterns
        
    def _extract_comment_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract comment patterns from the AST."""
        comments = []
        
        def collect_comments(node):
            if isinstance(node, dict):
                if node.get('type') == 'comment_block':
                    comments.append({
                        'type': 'block',
                        'content': node.get('content', '')
                    })
                elif node.get('type') == 'comment':
                    comments.append({
                        'type': 'inline',
                        'content': node.get('content', '')
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    collect_comments(child)
                    
        collect_comments(ast)
        
        return comments
        
    def _detect_naming_conventions(self, names: List[str]) -> List[str]:
        """Detect naming conventions in a list of names."""
        if not names:
            return []
            
        conventions = []
        
        # Check for camelCase
        if any(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name) for name in names):
            conventions.append("camelCase")
            
        # Check for snake_case
        if any(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("snake_case")
            
        # Check for kebab-case
        if any(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name for name in names):
            conventions.append("kebab-case")
            
        # Check for PascalCase
        if any(re.match(r'^[A-Z][a-zA-Z0-9]*$', name) for name in names):
            conventions.append("PascalCase")
            
        # Check for UPPER_CASE
        if any(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name for name in names):
            conventions.append("UPPER_CASE")
            
        # Check for lowercase
        if any(re.match(r'^[a-z][a-z0-9]*$', name) for name in names):
            conventions.append("lowercase")
            
        # Determine the most common convention
        if conventions:
            convention_counts = Counter(
                convention for name in names for convention in conventions 
                if self._matches_convention(name, convention)
            )
            
            if convention_counts:
                dominant_convention = convention_counts.most_common(1)[0][0]
                return [dominant_convention]
                
        return conventions
        
    def _matches_convention(self, name: str, convention: str) -> bool:
        """Check if a name matches a specific naming convention."""
        if convention == "camelCase":
            return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name))
        elif convention == "snake_case":
            return bool(re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name)
        elif convention == "kebab-case":
            return bool(re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name)
        elif convention == "PascalCase":
            return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
        elif convention == "UPPER_CASE":
            return bool(re.match(r'^[A-Z][A-Z0-9_]*$', name) and '_' in name)
        elif convention == "lowercase":
            return bool(re.match(r'^[a-z][a-z0-9]*$', name))
        return False 