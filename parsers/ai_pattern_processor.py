"""AI pattern processing management.

This module provides AI-powered pattern processing capabilities,
integrating with the parser system and AI tools infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    PatternCategory, PatternPurpose, PatternValidationResult,
    AIProcessingResult
)
from parsers.base_parser import BaseParser
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
from utils.request_cache import request_cache_context, cached_in_request
from db.transaction import transaction_scope
import traceback

@dataclass
class AIPatternProcessor(BaseParser):
    """AI pattern processing management.
    
    This class manages AI-powered pattern processing,
    integrating with the parser system and AI tools.
    
    Attributes:
        language_id (str): The identifier for the language
        capabilities (Set[AICapability]): Set of supported AI capabilities
        _pattern_cache (UnifiedCache): Cache for AI-generated patterns
    """
    
    def __init__(self, language_id: str):
        """Initialize AI pattern processor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.capabilities = set()
        self._pattern_cache = None
        self._processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "processing_times": []
        }
        
        # Tree-sitter related properties
        self._tree_sitter_parser = None
        self._query_registry = None
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize AI pattern processor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"ai_pattern_processor_initialization_{self.language_id}"):
                # Initialize cache
                self._pattern_cache = UnifiedCache(f"ai_pattern_processor_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"ai_pattern_processor_{self.language_id}",
                    self._pattern_cache
                )
                
                # Initialize tree-sitter components if available
                from parsers.tree_sitter_parser import get_tree_sitter_parser, QueryPatternRegistry
                self._tree_sitter_parser = await get_tree_sitter_parser(self.language_id)
                if self._tree_sitter_parser:
                    # Initialize query registry
                    self._query_registry = QueryPatternRegistry(self.language_id)
                    await self._query_registry.initialize()
                    await log(f"Tree-sitter initialized for AI pattern processor", level="info")
                
                # Load capabilities through async_runner
                init_task = submit_async_task(self._load_capabilities())
                await asyncio.wrap_future(init_task)
                
                if not self.capabilities:
                    raise ProcessingError(f"Failed to load capabilities for {self.language_id}")
                
                # Initialize AI tools
                from ai_tools.ai_interface import AIAssistant
                self._ai_assistant = await AIAssistant.create()
                
                await log(
                    f"AI pattern processor initialized for {self.language_id}", 
                    level="info",
                    context={
                        "component": "ai_pattern_processor",
                        "language_id": self.language_id,
                        "capabilities_count": len(self.capabilities),
                        "tree_sitter_available": self._tree_sitter_parser is not None
                    }
                )
                return True
                
        except Exception as e:
            await log(
                f"Error initializing AI pattern processor: {e}", 
                level="error", 
                context={
                    "component": "ai_pattern_processor",
                    "language_id": self.language_id,
                    "operation": "initialization",
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            await ErrorAudit.record_error(
                e,
                f"ai_pattern_processor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"processor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize AI pattern processor for {self.language_id}: {e}")
    
    async def _load_capabilities(self) -> None:
        """Load supported AI capabilities from storage."""
        try:
            # Update health status
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "loading_capabilities"}
            )
            
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_capabilities_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load capabilities
                capabilities_result = await txn.fetch("""
                    SELECT capability FROM language_ai_capabilities
                    WHERE language_id = $1
                """, self.language_id)
                
                if capabilities_result:
                    self.capabilities = {AICapability(row["capability"]) for row in capabilities_result}
                
                # Record transaction metrics
                await txn.record_operation("load_capabilities_complete", {
                    "language_id": self.language_id,
                    "capabilities_count": len(self.capabilities),
                    "end_time": time.time()
                })
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    f"ai_pattern_processor_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "capabilities_loaded": bool(capabilities_result),
                        "capabilities_count": len(self.capabilities)
                    }
                )
                    
        except Exception as e:
            await log(f"Error loading capabilities: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            raise ProcessingError(f"Failed to load capabilities: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def process_pattern(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process a pattern using AI capabilities.
        
        Args:
            pattern_name: The name of the pattern to process
            content: The content to process
            context: The AI processing context
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"ai_pattern_processing_{self.language_id}"):
                # Check cache first
                cache_key = f"pattern:{self.language_id}:{pattern_name}:{hash(content)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Process through async_runner
                process_task = submit_async_task(
                    self._process_with_ai(pattern_name, content, context)
                )
                result = await asyncio.wrap_future(process_task)
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(f"Pattern processed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error processing pattern: {e}", level="error")
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"ai_pattern_processing_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "content_size": len(content)
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _process_with_ai(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process pattern with AI assistance."""
        try:
            start_time = time.time()
            
            # Get AI response
            response = await self._ai_assistant.process_pattern(
                pattern_name,
                content,
                self.language_id,
                context
            )
            
            # Update timing stats
            processing_time = time.time() - start_time
            self._processing_stats["processing_times"].append(processing_time)
            
            return PatternValidationResult(
                is_valid=response.success,
                errors=response.errors if not response.success else [],
                validation_time=processing_time
            )
            
        except Exception as e:
            await log(f"Error in AI processing: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _cleanup(self) -> None:
        """Clean up AI pattern processor resources."""
        try:
            # Clean up cache
            if self._pattern_cache:
                await cache_coordinator.unregister_cache(f"ai_pattern_processor_{self.language_id}")
                self._pattern_cache = None
            
            # Save processing stats
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO ai_pattern_processor_stats (
                        timestamp, language_id,
                        total_processed, successful_processing,
                        failed_processing, avg_processing_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._processing_stats["total_processed"],
                    self._processing_stats["successful_processing"],
                    self._processing_stats["failed_processing"],
                    sum(self._processing_stats["processing_times"]) / len(self._processing_stats["processing_times"])
                    if self._processing_stats["processing_times"] else 0
                ))
            
            await log(f"AI pattern processor cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up AI pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup AI pattern processor: {e}")

    @handle_async_errors(error_types=ProcessingError)
    async def analyze_with_tree_sitter(
        self,
        content: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Analyze code with tree-sitter and AI.
        
        Args:
            content: The content to analyze
            context: The AI processing context
            
        Returns:
            AIProcessingResult: The AI processing result
        """
        try:
            async with AsyncErrorBoundary(f"ai_tree_sitter_analysis_{self.language_id}"):
                # Check if tree-sitter parser is available
                if not self._tree_sitter_parser:
                    return AIProcessingResult(
                        success=False,
                        errors=["Tree-sitter parser not available for this language"]
                    )
                
                # Check cache first - use a combined hash of content and context attributes
                context_hash = hash(str(context.__dict__))
                cache_key = f"ts_analysis:{self.language_id}:{hash(content)}:{context_hash}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return AIProcessingResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Parse with optimized tree-sitter method
                start_time = time.time()
                tree = await self._tree_sitter_parser._parse_with_tree_sitter(content)
                
                if not tree:
                    return AIProcessingResult(
                        success=False,
                        errors=["Failed to parse content with tree-sitter"]
                    )
                
                # Extract comprehensive structured information
                structured_data = await self._extract_comprehensive_data(tree, content)
                
                # Track tree-sitter processing time
                tree_sitter_time = time.time() - start_time
                
                # Enhance AI context with structured data and performance metrics
                enhanced_context = AIContext(
                    **context.__dict__,
                    structured_code=structured_data,
                    performance_metrics={
                        "tree_sitter_processing_time": tree_sitter_time
                    }
                )
                
                # Process with AI
                ai_start_time = time.time()
                response = await self._ai_assistant.process_with_structure(
                    content,
                    structured_data,
                    self.language_id,
                    enhanced_context
                )
                ai_processing_time = time.time() - ai_start_time
                
                # Add processing times to response
                if not hasattr(response, 'performance_metrics') or not response.performance_metrics:
                    response.performance_metrics = {}
                
                response.performance_metrics["tree_sitter_time"] = tree_sitter_time
                response.performance_metrics["ai_processing_time"] = ai_processing_time
                response.performance_metrics["total_time"] = tree_sitter_time + ai_processing_time
                
                # Cache the result
                await self._pattern_cache.set(cache_key, response.__dict__)
                
                # Update processing stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(
                    f"Completed tree-sitter AI analysis for {self.language_id}", 
                    level="info",
                    context={
                        "component": "ai_pattern_processor",
                        "language_id": self.language_id,
                        "operation": "analyze_with_tree_sitter",
                        "tree_sitter_time": tree_sitter_time,
                        "ai_processing_time": ai_processing_time,
                        "structured_data_size": len(str(structured_data)),
                        "content_size": len(content)
                    }
                )
                
                return response
                
        except Exception as e:
            await log(
                f"Error in AI tree-sitter analysis: {e}", 
                level="error",
                context={
                    "component": "ai_pattern_processor",
                    "language_id": self.language_id,
                    "operation": "analyze_with_tree_sitter",
                    "content_size": len(content),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            self._processing_stats["failed_processing"] += 1
            return AIProcessingResult(
                success=False,
                errors=[str(e)]
            )
    
    async def _extract_comprehensive_data(self, tree: Any, content: str) -> Dict[str, Any]:
        """Extract comprehensive structured data from tree-sitter tree.
        
        This method combines multiple tree-sitter features to create a rich
        structured representation of the code for AI analysis.
        
        Args:
            tree: The tree-sitter tree
            content: The source code
            
        Returns:
            Dict[str, Any]: Comprehensive structured data
        """
        structured_data = {}
        
        try:
            # Get basic tree-sitter features
            base_features = await self._tree_sitter_parser._extract_tree_sitter_features(tree)
            structured_data.update(base_features)
            
            # Add syntax structure
            structured_data["syntax_structure"] = self._tree_sitter_parser._extract_structural_features(tree.root_node)
            
            # Add error information if any
            error_info = await self._tree_sitter_parser._extract_error_information(tree.root_node)
            if error_info:
                structured_data["syntax_errors"] = error_info
            
            # Add node statistics
            structured_data["node_statistics"] = {
                "counts": self._tree_sitter_parser._count_node_types(tree.root_node),
                "total_nodes": self._tree_sitter_parser._count_nodes(tree.root_node),
                "max_depth": self._tree_sitter_parser._calculate_max_depth(tree.root_node)
            }
            
            # Add complexity metrics
            structured_data["complexity"] = {
                "cyclomatic": self._count_decision_points(tree.root_node),
                "nesting": self._calculate_max_nesting(tree.root_node),
                "function_complexity": self._calculate_function_complexity(tree.root_node)
            }
            
            # Add important nodes based on predefined queries
            if self._query_registry:
                # Get available pattern categories
                for category in self._query_registry.get_all_patterns().keys():
                    query_string = self._query_registry.get_pattern(category)
                    if query_string:
                        # Execute query
                        query_results = await self._tree_sitter_parser._execute_query(query_string, tree)
                        if query_results:
                            structured_data[f"{category}_nodes"] = query_results
            
            # Add code structure summary
            structured_data["code_structure"] = {
                "functions": self._extract_functions(tree.root_node, content),
                "classes": self._extract_classes(tree.root_node, content),
                "imports": self._extract_imports(tree.root_node, content)
            }
            
        except Exception as e:
            await log(f"Error extracting comprehensive data: {e}", level="warning")
            # Return what we've gathered so far
            structured_data["extraction_error"] = str(e)
            
        return structured_data
    
    def _count_decision_points(self, node: Any) -> int:
        """Count decision points in code (for cyclomatic complexity).
        
        Args:
            node: The tree-sitter node
            
        Returns:
            int: Number of decision points
        """
        decision_count = 0
        decision_nodes = [
            "if_statement", "while_statement", "for_statement", 
            "switch_statement", "case_statement", "conditional_expression",
            "ternary_expression", "&&", "||"
        ]
        
        # Count this node if it's a decision point
        if node.type in decision_nodes:
            decision_count += 1
        
        # Recursively count children
        for child in node.children:
            decision_count += self._count_decision_points(child)
            
        return decision_count
    
    def _calculate_max_nesting(self, node: Any) -> int:
        """Calculate maximum nesting level.
        
        Args:
            node: The tree-sitter node
            
        Returns:
            int: Maximum nesting level
        """
        nesting_nodes = [
            "if_statement", "for_statement", "while_statement",
            "function_definition", "method_definition", "class_definition",
            "try_statement", "catch_clause", "block"
        ]
        
        if not node.children:
            return 0
            
        if node.type in nesting_nodes:
            return 1 + max([self._calculate_max_nesting(child) for child in node.children], default=0)
        else:
            return max([self._calculate_max_nesting(child) for child in node.children], default=0)
    
    def _calculate_function_complexity(self, node: Any) -> Dict[str, Any]:
        """Calculate function complexity metrics.
        
        Args:
            node: The tree-sitter node
            
        Returns:
            Dict[str, Any]: Function complexity metrics
        """
        function_metrics = {}
        
        # Find function definitions
        function_types = ["function_definition", "method_definition", "arrow_function"]
        
        if node.type in function_types:
            # Get function name if available
            name = None
            for child in node.children:
                if child.type == "identifier":
                    name = child.text.decode('utf-8') if hasattr(child.text, 'decode') else child.text
                    break
            
            # Key for this function
            key = name or f"{node.type}_{node.start_point[0]}_{node.start_point[1]}"
            
            # Calculate metrics for this function
            function_metrics[key] = {
                "cyclomatic": self._count_decision_points(node),
                "nesting": self._calculate_max_nesting(node),
                "lines": node.end_point[0] - node.start_point[0] + 1,
                "type": node.type
            }
        
        # Recursively process children
        for child in node.children:
            child_metrics = self._calculate_function_complexity(child)
            function_metrics.update(child_metrics)
            
        return function_metrics
    
    def _extract_functions(self, node: Any, content: str) -> List[Dict[str, Any]]:
        """Extract function information.
        
        Args:
            node: The tree-sitter node
            content: The source code
            
        Returns:
            List[Dict[str, Any]]: List of function information
        """
        functions = []
        
        function_types = ["function_definition", "method_definition", "arrow_function"]
        
        if node.type in function_types:
            # Extract basic function info
            func_info = {
                "type": node.type,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "complexity": self._count_decision_points(node)
            }
            
            # Get function name if available
            for child in node.children:
                if child.type == "identifier":
                    func_info["name"] = child.text.decode('utf-8') if hasattr(child.text, 'decode') else child.text
                    break
            
            # Get parameters if available
            params = []
            for child in node.children:
                if child.type == "parameter_list" or child.type == "formal_parameters":
                    for param_child in child.children:
                        if param_child.type == "identifier" or param_child.type == "parameter":
                            param_text = param_child.text.decode('utf-8') if hasattr(param_child.text, 'decode') else param_child.text
                            params.append(param_text)
            
            if params:
                func_info["parameters"] = params
            
            # Add function content
            start_byte = node.start_byte
            end_byte = node.end_byte
            if isinstance(content, str) and start_byte < len(content) and end_byte <= len(content):
                func_info["content"] = content[start_byte:end_byte]
            
            functions.append(func_info)
        
        # Recursively process children
        for child in node.children:
            child_functions = self._extract_functions(child, content)
            functions.extend(child_functions)
            
        return functions
    
    def _extract_classes(self, node: Any, content: str) -> List[Dict[str, Any]]:
        """Extract class information.
        
        Args:
            node: The tree-sitter node
            content: The source code
            
        Returns:
            List[Dict[str, Any]]: List of class information
        """
        classes = []
        
        class_types = ["class_definition", "class_declaration"]
        
        if node.type in class_types:
            # Extract basic class info
            class_info = {
                "type": node.type,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1
            }
            
            # Get class name if available
            for child in node.children:
                if child.type == "identifier":
                    class_info["name"] = child.text.decode('utf-8') if hasattr(child.text, 'decode') else child.text
                    break
            
            # Get superclasses if available
            superclasses = []
            for child in node.children:
                if child.type == "extends_clause" or child.type == "superclass" or child.type == "argument_list":
                    for super_child in child.children:
                        if super_child.type == "identifier" or super_child.type == "type_identifier":
                            super_text = super_child.text.decode('utf-8') if hasattr(super_child.text, 'decode') else super_child.text
                            superclasses.append(super_text)
            
            if superclasses:
                class_info["superclasses"] = superclasses
            
            # Find all methods in this class
            class_info["methods"] = []
            for child in node.children:
                if child.type == "body" or child.type == "class_body":
                    methods = self._extract_functions(child, content)
                    class_info["methods"] = methods
            
            # Add class content
            start_byte = node.start_byte
            end_byte = node.end_byte
            if isinstance(content, str) and start_byte < len(content) and end_byte <= len(content):
                class_info["content"] = content[start_byte:end_byte]
            
            classes.append(class_info)
        
        # Recursively process children
        for child in node.children:
            child_classes = self._extract_classes(child, content)
            classes.extend(child_classes)
            
        return classes
    
    def _extract_imports(self, node: Any, content: str) -> List[Dict[str, Any]]:
        """Extract import information.
        
        Args:
            node: The tree-sitter node
            content: The source code
            
        Returns:
            List[Dict[str, Any]]: List of import information
        """
        imports = []
        
        import_types = ["import_statement", "import_declaration", "using_directive", "include_statement"]
        
        if node.type in import_types:
            # Extract basic import info
            import_info = {
                "type": node.type,
                "line": node.start_point[0] + 1
            }
            
            # Add import content
            start_byte = node.start_byte
            end_byte = node.end_byte
            if isinstance(content, str) and start_byte < len(content) and end_byte <= len(content):
                import_info["content"] = content[start_byte:end_byte]
            
            imports.append(import_info)
        
        # Recursively process children
        for child in node.children:
            child_imports = self._extract_imports(child, content)
            imports.extend(child_imports)
            
        return imports

    @handle_async_errors(error_types=ProcessingError)
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process source code with AI assistance.
        
        This method implements the AIParserInterface requirement for
        AI-powered source code processing.
        
        Args:
            source_code: The source code to process
            context: The AI processing context
            
        Returns:
            PatternValidationResult: The processing result
            
        Raises:
            ProcessingError: If processing fails
        """
        try:
            async with AsyncErrorBoundary(f"ai_process_code_{self.language_id}"):
                # Check cache first
                cache_key = f"ai_process:{self.language_id}:{hash(source_code)}:{hash(str(context.__dict__))}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # If tree-sitter is available, first analyze with tree-sitter
                enhanced_context = context
                if self._tree_sitter_parser:
                    # Use tree-sitter to extract structural information
                    analysis_result = await self.analyze_with_tree_sitter(source_code, context)
                    if analysis_result.success:
                        # Enhance context with tree-sitter analysis
                        enhanced_context = AIContext(
                            **context.__dict__,
                            structured_data=analysis_result.structured_data
                        )
                
                # Process with AI
                start_time = time.time()
                response = await self._ai_assistant.process_code(
                    source_code,
                    self.language_id,
                    enhanced_context
                )
                
                # Create result
                result = PatternValidationResult(
                    is_valid=response.success,
                    errors=response.errors if not response.success else [],
                    validation_time=time.time() - start_time,
                    matches=response.matches if hasattr(response, 'matches') else []
                )
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(
                    f"Code processed with AI for {self.language_id}", 
                    level="info",
                    context={
                        "component": "ai_pattern_processor",
                        "language_id": self.language_id,
                        "operation": "process_with_ai",
                        "source_code_size": len(source_code),
                        "processing_time": time.time() - start_time
                    }
                )
                
                return result
                
        except Exception as e:
            await log(
                f"Error processing code with AI: {e}", 
                level="error",
                context={
                    "component": "ai_pattern_processor",
                    "language_id": self.language_id,
                    "operation": "process_with_ai",
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"ai_process_code_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    @handle_async_errors(error_types=ProcessingError)
    async def learn_from_code(
        self,
        source_code: str,
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Learn patterns from source code.
        
        This method implements the AIParserInterface requirement for
        learning capabilities. It analyzes source code to identify
        patterns that can be used for future processing.
        
        Args:
            source_code: The source code to learn from
            context: The AI learning context
            
        Returns:
            List[Dict[str, Any]]: The learned patterns
            
        Raises:
            ProcessingError: If learning fails
        """
        try:
            async with AsyncErrorBoundary(f"ai_learn_from_code_{self.language_id}"):
                # Check cache first
                cache_key = f"learn_patterns:{self.language_id}:{hash(source_code)}:{hash(str(context.__dict__))}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return cached_result
                
                self._processing_stats["cache_misses"] += 1
                
                # Extract structured data from code if tree-sitter is available
                structured_data = None
                if self._tree_sitter_parser:
                    start_time = time.time()
                    tree = await self._tree_sitter_parser._parse_with_tree_sitter(source_code)
                    
                    if tree:
                        # Extract comprehensive structured information
                        structured_data = await self._extract_comprehensive_data(tree, source_code)
                        await log(
                            f"Extracted structured data for learning in {time.time() - start_time:.2f}s",
                            level="debug",
                            context={
                                "component": "ai_pattern_processor",
                                "language_id": self.language_id,
                                "operation": "learn_from_code",
                                "tree_sitter_time": time.time() - start_time
                            }
                        )
                
                # Learn patterns with AI
                start_time = time.time()
                
                # If we have structured data, add it to the context
                if structured_data:
                    enhanced_context = AIContext(
                        **context.__dict__,
                        structured_data=structured_data
                    )
                else:
                    enhanced_context = context
                
                # Use AI to learn patterns
                learned_patterns = await self._ai_assistant.learn_patterns(
                    source_code,
                    self.language_id,
                    enhanced_context
                )
                
                learning_time = time.time() - start_time
                
                # Process and validate learned patterns
                validated_patterns = []
                for pattern in learned_patterns:
                    # Validate and normalize pattern
                    try:
                        # Add metadata
                        pattern["language_id"] = self.language_id
                        pattern["learned"] = True
                        pattern["learning_timestamp"] = time.time()
                        
                        # Add to validated patterns
                        validated_patterns.append(pattern)
                    except Exception as e:
                        await log(f"Error validating learned pattern: {e}", level="warning")
                
                # Store learned patterns in database
                if validated_patterns:
                    await self._store_learned_patterns(validated_patterns)
                
                # Cache result
                await self._pattern_cache.set(cache_key, validated_patterns)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(
                    f"Learned {len(validated_patterns)} patterns from code for {self.language_id}",
                    level="info",
                    context={
                        "component": "ai_pattern_processor",
                        "language_id": self.language_id,
                        "operation": "learn_from_code",
                        "patterns_count": len(validated_patterns),
                        "learning_time": learning_time,
                        "source_code_size": len(source_code)
                    }
                )
                
                return validated_patterns
                
        except Exception as e:
            await log(
                f"Error learning from code: {e}",
                level="error",
                context={
                    "component": "ai_pattern_processor",
                    "language_id": self.language_id,
                    "operation": "learn_from_code",
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"ai_learn_from_code_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            raise ProcessingError(f"Failed to learn from code: {e}")
            
    async def _store_learned_patterns(self, patterns: List[Dict[str, Any]]) -> None:
        """Store learned patterns in the database.
        
        Args:
            patterns: List of learned patterns to store
        """
        try:
            async with transaction_scope() as txn:
                for pattern in patterns:
                    # Generate a unique name for the learned pattern
                    pattern_name = f"learned_{self.language_id}_{int(time.time())}_{hash(str(pattern)) % 10000}"
                    
                    # Store pattern in database
                    await txn.execute("""
                        INSERT INTO learned_patterns (
                            language_id, pattern_name, pattern_data,
                            learned_timestamp, source
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (language_id, pattern_name) 
                        DO UPDATE SET pattern_data = $3, learned_timestamp = $4
                    """, (
                        self.language_id,
                        pattern_name,
                        pattern,
                        time.time(),
                        "ai_learning"
                    ))
        except Exception as e:
            await log(f"Error storing learned patterns: {e}", level="error")

# Global instance cache
_processor_instances: Dict[str, AIPatternProcessor] = {}

async def get_ai_pattern_processor(language_id: str) -> Optional[AIPatternProcessor]:
    """Get an AI pattern processor instance.
    
    Args:
        language_id: The language to get processor for
        
    Returns:
        Optional[AIPatternProcessor]: The processor instance or None if initialization fails
    """
    if language_id not in _processor_instances:
        processor = AIPatternProcessor(language_id)
        if await processor.initialize():
            _processor_instances[language_id] = processor
        else:
            return None
    return _processor_instances[language_id]

# Export public interfaces
__all__ = [
    'AIPatternProcessor',
    'get_ai_pattern_processor',
    'ai_pattern_processor'
] 