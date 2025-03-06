from .base_imports import *
import json
import re
from collections import Counter

class JsonParser(BaseParser, CustomParserMixin):
    """Parser for JSON files with enhanced documentation and structure analysis."""

    def __init__(self, language_id: str = "json", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.DATA, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING
        }
        register_shutdown_handler(self.cleanup)

    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("JSON parser initialization"):
                    # Initialize base resources
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("JSON parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing JSON parser: {e}", level="error")
                raise
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> JsonNodeDict:
        """Create a standardized JSON AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "value": kwargs.get("value"),
            "path": kwargs.get("path")
        }

    def _process_json_value(
        self, 
        value: Any, 
        path: str, 
        parent_key: Optional[str] = None
    ) -> JsonNodeDict:
        """Process a JSON value into a node structure."""
        if isinstance(value, dict):
            node = self._create_node(
                "object",
                [0, 0],  # Placeholder positions
                [0, 0],
                path=path,
                children=[],
                keys=list(value.keys()),
                key_ordering=list(value.keys()),
                parent_key=parent_key,
                schema_type="object"
            )
            
            for key, item in value.items():
                child_path = f"{path}.{key}" if path else key
                child = self._process_json_value(item, child_path, key)
                node["children"].append(child)
                
            return node
            
        elif isinstance(value, list):
            node = self._create_node(
                "array",
                [0, 0],  # Placeholder positions
                [0, 0],
                path=path,
                children=[],
                items_count=len(value),
                parent_key=parent_key,
                schema_type="array"
            )
            
            for idx, item in enumerate(value):
                child_path = f"{path}[{idx}]" if path else f"[{idx}]"
                child = self._process_json_value(item, child_path)
                node["children"].append(child)
                
            return node
            
        else:
            # Determine the schema type
            if value is None:
                schema_type = "null"
            elif isinstance(value, bool):
                schema_type = "boolean"
            elif isinstance(value, int):
                schema_type = "integer"
            elif isinstance(value, float):
                schema_type = "number"
            elif isinstance(value, str):
                schema_type = "string"
                # Check if it's a special format
                if re.match(r'^\d{4}-\d{2}-\d{2}', value):
                    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', value):
                        schema_type = "string:datetime"
                    else:
                        schema_type = "string:date"
                elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value, re.I):
                    schema_type = "string:uuid"
                elif re.match(r'^https?://', value):
                    schema_type = "string:uri"
                elif re.match(r'^[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}$', value):
                    schema_type = "string:email"
            else:
                schema_type = "unknown"
                
            return self._create_node(
                "value",
                [0, 0],  # Placeholder positions
                [0, 0],
                path=path,
                parent_key=parent_key,
                schema_type=schema_type,
                value=value,
                value_type=type(value).__name__
            )

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse JSON content into AST structure with caching support."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("JSON parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                # Note: We don't need to check cache here as BaseParser.parse() already does this
                # This method will only be called for cache misses
                
                task = asyncio.create_task(json.loads(source_code))
                self._pending_tasks.add(task)
                try:
                    data = await task
                finally:
                    self._pending_tasks.remove(task)
                
                ast = self._process_json_value(data, "")
                
                # Set document root position
                ast["start_point"] = [0, 0]
                ast["end_point"] = [len(source_code.splitlines()), 0]
                
                # Analyze structure
                self._analyze_structure(ast)
                
                return ast
                
            except json.JSONDecodeError as e:
                log(f"Error parsing JSON: {e}", level="error")
                return None
            except Exception as e:
                log(f"Unexpected error parsing JSON: {e}", level="error")
                return None

    def _analyze_structure(self, node: JsonNodeDict) -> None:
        """Analyze JSON structure for insights."""
        if node["type"] == "object":
            # Analyze naming conventions
            if node["keys"]:
                conventions = self._detect_naming_convention(node["keys"])
                node["metadata"]["naming_convention"] = conventions[0] if conventions else "mixed"
                node["metadata"]["naming_conventions"] = conventions
                
            # Analyze nesting
            max_depth = 0
            for child in node["children"]:
                self._analyze_structure(child)
                child_depth = child["metadata"].get("max_depth", 0)
                max_depth = max(max_depth, child_depth + 1)
            node["metadata"]["max_depth"] = max_depth
                
        elif node["type"] == "array":
            # Analyze homogeneity
            schema_types = [child["schema_type"] for child in node["children"]]
            if schema_types:
                is_homogeneous = len(set(schema_types)) == 1
                node["metadata"]["is_homogeneous"] = is_homogeneous
                node["metadata"]["item_type"] = schema_types[0] if is_homogeneous else "mixed"
                
            # Analyze nesting
            max_depth = 0
            for child in node["children"]:
                self._analyze_structure(child)
                child_depth = child["metadata"].get("max_depth", 0)
                max_depth = max(max_depth, child_depth + 1)
            node["metadata"]["max_depth"] = max_depth
                
        else:  # value node
            node["metadata"]["max_depth"] = 0
    
    def _detect_naming_convention(self, keys: List[str]) -> List[str]:
        """Detect naming conventions in a list of keys."""
        conventions = []
        
        # Check for camelCase
        if any(re.match(r'^[a-z][a-zA-Z0-9]*$', key) and any(c.isupper() for c in key) for key in keys):
            conventions.append("camelCase")
            
        # Check for snake_case
        if any(re.match(r'^[a-z][a-z0-9_]*$', key) and '_' in key for key in keys):
            conventions.append("snake_case")
            
        # Check for kebab-case
        if any(re.match(r'^[a-z][a-z0-9-]*$', key) and '-' in key for key in keys):
            conventions.append("kebab-case")
            
        # Check for PascalCase
        if any(re.match(r'^[A-Z][a-zA-Z0-9]*$', key) for key in keys):
            conventions.append("PascalCase")
            
        # Check for UPPER_CASE
        if any(re.match(r'^[A-Z][A-Z0-9_]*$', key) and '_' in key for key in keys):
            conventions.append("UPPER_CASE")
            
        return conventions

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract JSON patterns from the source code for repository learning.
        
        Args:
            source_code: The content of the JSON file
            
        Returns:
            List of extracted patterns with metadata
        """
        patterns = []
        
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("JSON pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Parse the source first to get a structured representation
                task = asyncio.create_task(self._parse_source(source_code))
                self._pending_tasks.add(task)
                try:
                    ast = await task
                finally:
                    self._pending_tasks.remove(task)
                
                if not ast:
                    return []
                
                # Extract structure patterns
                patterns.extend(self._extract_structure_patterns(ast))
                
                # Extract naming convention patterns
                patterns.extend(self._extract_naming_convention_patterns(ast))
                
                # Extract schema patterns
                patterns.extend(self._extract_schema_patterns(ast))
                
                # Extract common field patterns
                patterns.extend(self._extract_common_field_patterns(ast))
                
                # Extract nested structure patterns
                patterns.extend(self._extract_nested_structure_patterns(ast))
                
                return patterns
                
            except Exception as e:
                log(f"Error extracting JSON patterns: {e}", level="error")
                return []
        
    def _extract_structure_patterns(self, ast: JsonNodeDict) -> List[Dict[str, Any]]:
        """Extract structure patterns from the AST."""
        patterns = []
        
        # Analyze overall structure
        if ast["type"] == "object":
            # Root level object structure
            patterns.append({
                'name': 'json_root_structure',
                'content': json.dumps({'root_keys': ast["keys"]}, indent=2),
                'pattern_type': PatternType.DATA_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'root_keys': ast["keys"],
                    'max_depth': ast["metadata"].get('max_depth', 0)
                }
            })
            
            # Check for configuration file patterns
            if self._is_likely_config_file(ast):
                patterns.append({
                    'name': 'json_config_file',
                    'content': json.dumps({'type': 'configuration_file'}, indent=2),
                    'pattern_type': PatternType.FILE_TYPE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'file_type': 'configuration',
                        'config_sections': self._extract_config_sections(ast)
                    }
                })
                
        elif ast["type"] == "array":
            # Root level array structure
            item_types = self._analyze_array_item_types(ast)
            patterns.append({
                'name': 'json_array_structure',
                'content': json.dumps({'root_structure': 'array', 'item_types': item_types}, indent=2),
                'pattern_type': PatternType.DATA_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'is_homogeneous': ast["metadata"].get('is_homogeneous', False),
                    'item_type': ast["metadata"].get('item_type', 'mixed'),
                    'items_count': ast["items_count"],
                    'item_types': item_types
                }
            })
            
            # Check for data collection pattern
            if self._is_likely_data_collection(ast):
                patterns.append({
                    'name': 'json_data_collection',
                    'content': json.dumps({'type': 'data_collection'}, indent=2),
                    'pattern_type': PatternType.FILE_TYPE,
                    'language': self.language_id,
                    'confidence': 0.85,
                    'metadata': {
                        'file_type': 'data_collection',
                        'item_count': ast["items_count"],
                        'common_fields': self._extract_common_fields(ast)
                    }
                })
                
        # Extract nested structure patterns
        nested_patterns = self._extract_nested_structure_patterns(ast)
        patterns.extend(nested_patterns)
        
        return patterns
        
    def _extract_naming_convention_patterns(self, ast: JsonNodeDict) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        patterns = []
        conventions = {}
        
        def collect_conventions(node):
            if node["type"] == "object" and node["metadata"].get("naming_convention"):
                convention = node["metadata"]["naming_convention"]
                if convention != "mixed":
                    conventions[convention] = conventions.get(convention, 0) + 1
            
            for child in node["children"]:
                collect_conventions(child)
                
        collect_conventions(ast)
        
        # Create patterns for dominant naming conventions
        if conventions:
            dominant_convention = max(conventions.items(), key=lambda x: x[1])[0]
            patterns.append({
                'name': f'json_naming_convention_{dominant_convention}',
                'content': f"JSON naming convention: {dominant_convention}",
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': min(0.7 + (conventions[dominant_convention] / 10), 0.95),
                'metadata': {
                    'convention': dominant_convention,
                    'frequency': conventions[dominant_convention],
                    'all_conventions': conventions
                }
            })
            
        return patterns
        
    def _extract_schema_patterns(self, ast: JsonNodeDict) -> List[Dict[str, Any]]:
        """Extract schema patterns from the AST."""
        patterns = []
        
        # Extract common schema patterns based on field types and structures
        field_schemas = {}
        
        def collect_field_schemas(node, path=""):
            if node["type"] == "object":
                for child in node["children"]:
                    child_path = f"{path}.{child['parent_key']}" if path else child['parent_key']
                    if child["type"] == "value":
                        field_schemas[child_path] = child["schema_type"]
                    collect_field_schemas(child, child_path)
            elif node["type"] == "array" and node["children"] and node["metadata"].get("is_homogeneous", False):
                sample_child = node["children"][0]
                if sample_child["type"] == "object":
                    collect_field_schemas(sample_child, f"{path}[item]")
                
        collect_field_schemas(ast)
        
        if field_schemas:
            patterns.append({
                'name': 'json_schema_fields',
                'content': json.dumps(field_schemas, indent=2),
                'pattern_type': PatternType.DATA_SCHEMA,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'field_schemas': field_schemas
                }
            })
            
            # Check for special schema types
            special_types = {k: v for k, v in field_schemas.items() 
                            if ':' in v and v.startswith('string:')}
            if special_types:
                patterns.append({
                    'name': 'json_special_field_types',
                    'content': json.dumps(special_types, indent=2),
                    'pattern_type': PatternType.DATA_SCHEMA,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'special_field_types': special_types
                    }
                })
                
        return patterns
        
    def _extract_common_field_patterns(self, ast: JsonNodeDict) -> List[Dict[str, Any]]:
        """Extract common field patterns from the AST."""
        patterns = []
        common_fields = set()
        
        def collect_fields(node, field_set=None):
            if field_set is None:
                field_set = set()
                
            if node["type"] == "object":
                field_set.update(node["keys"])
                
            for child in node["children"]:
                collect_fields(child, field_set)
                
            return field_set
            
        # Collect all fields
        all_fields = collect_fields(ast)
        
        # Identify common fields
        common_patterns = [
            ('id', 'identifier_field', ['id', '_id', 'uuid', 'guid']),
            ('timestamp', 'timestamp_field', ['created_at', 'updated_at', 'timestamp', 'date', 'time', 'created', 'updated']),
            ('user', 'user_field', ['user', 'user_id', 'author', 'owner', 'creator']),
            ('status', 'status_field', ['status', 'state', 'active', 'enabled', 'disabled']),
            ('type', 'type_field', ['type', 'kind', 'category', 'class']),
            ('version', 'version_field', ['version', 'v', 'rev', 'revision']),
            ('config', 'config_field', ['config', 'configuration', 'settings', 'options']),
            ('metadata', 'metadata_field', ['metadata', 'meta', 'info', 'data']),
            ('pagination', 'pagination_field', ['page', 'limit', 'offset', 'per_page', 'total']),
            ('error', 'error_field', ['error', 'errors', 'message', 'code', 'success'])
        ]
        
        for pattern_type, pattern_name, keywords in common_patterns:
            matching_fields = [field for field in all_fields if field.lower() in keywords]
            if matching_fields:
                patterns.append({
                    'name': f'json_{pattern_name}',
                    'content': json.dumps({pattern_type: matching_fields}, indent=2),
                    'pattern_type': PatternType.DATA_FIELD,
                    'language': self.language_id,
                    'confidence': 0.9,
                    'metadata': {
                        'field_type': pattern_type,
                        'matching_fields': matching_fields
                    }
                })
                
        return patterns
        
    def _is_likely_config_file(self, ast: JsonNodeDict) -> bool:
        """Check if this is likely a configuration file."""
        if ast["type"] != "object":
            return False
            
        # Configuration files typically have these keys or structures
        config_indicators = [
            'config', 'configuration', 'settings', 'options', 'preferences',
            'environment', 'env', 'development', 'production', 'staging',
            'debug', 'release', 'version'
        ]
        
        # Check for presence of common config keys
        for key in ast["keys"]:
            if key.lower() in config_indicators:
                return True
                
        # Check for nested configuration sections
        has_nested_objects = any(child["type"] == "object" for child in ast["children"])
        has_primitive_values = any(child["type"] == "value" for child in ast["children"])
        
        # Config files often have a mix of primitive values and nested objects
        return has_nested_objects and has_primitive_values
        
    def _extract_config_sections(self, ast: JsonNodeDict) -> List[str]:
        """Extract configuration sections from a config file."""
        if ast["type"] != "object":
            return []
            
        # Return top-level keys that are objects
        return [child["parent_key"] for child in ast["children"] 
                if child["type"] == "object" and child["parent_key"]]
                
    def _is_likely_data_collection(self, ast: JsonNodeDict) -> bool:
        """Check if this is likely a data collection."""
        if ast["type"] != "array" or not ast["children"]:
            return False
            
        # Data collections typically have array of objects
        is_array_of_objects = all(child["type"] == "object" for child in ast["children"])
        
        # And typically the objects share common fields
        if is_array_of_objects and len(ast["children"]) > 1:
            common_fields = self._extract_common_fields(ast)
            # If there are at least 2 common fields across items, it's likely a collection
            return len(common_fields) >= 2
            
        return False
        
    def _extract_common_fields(self, ast: JsonNodeDict) -> List[str]:
        """Extract common fields from an array of objects."""
        if ast["type"] != "array" or not ast["children"]:
            return []
            
        # Get all object children
        object_children = [child for child in ast["children"] if child["type"] == "object"]
        if not object_children:
            return []
            
        # Find fields that appear in most objects
        all_fields = Counter()
        for child in object_children:
            all_fields.update(child["keys"])
            
        # Return fields that appear in at least 70% of the objects
        threshold = 0.7 * len(object_children)
        return [field for field, count in all_fields.items() if count >= threshold]
        
    def _extract_nested_structure_patterns(self, ast: JsonNodeDict) -> List[Dict[str, Any]]:
        """Extract patterns from nested structures."""
        patterns = []
        
        def process_nested_objects(node, path=""):
            if node["type"] == "object" and len(node["keys"]) >= 3:
                # Found a significant nested object
                patterns.append({
                    'name': f'json_nested_object_{path.replace(".", "_")}',
                    'content': json.dumps({'path': path, 'keys': node["keys"]}, indent=2),
                    'pattern_type': PatternType.DATA_STRUCTURE,
                    'language': self.language_id,
                    'confidence': 0.8,
                    'metadata': {
                        'path': path,
                        'keys': node["keys"],
                        'depth': path.count('.') + 1
                    }
                })
                
            # Process children
            for child in node["children"]:
                if child["type"] in ["object", "array"]:
                    child_path = f"{path}.{child['parent_key']}" if path and child['parent_key'] else \
                               child['parent_key'] if child['parent_key'] else path
                    process_nested_objects(child, child_path)
                    
        process_nested_objects(ast)
        return patterns
        
    def _analyze_array_item_types(self, array_node: JsonNodeDict) -> Dict[str, int]:
        """Analyze the types of items in an array."""
        if array_node["type"] != "array":
            return {}
            
        type_counter = Counter()
        for child in array_node["children"]:
            type_counter[child["type"]] += 1
            
        return dict(type_counter)

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process JSON with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("JSON AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse JSON"
                    )
                
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._process_with_understanding(ast, context)
                    results.context_info.update(understanding)
                
                # Process with generation capability
                if AICapability.CODE_GENERATION in self.capabilities:
                    generation = await self._process_with_generation(ast, context)
                    results.suggestions.extend(generation)
                
                # Process with modification capability
                if AICapability.CODE_MODIFICATION in self.capabilities:
                    modification = await self._process_with_modification(ast, context)
                    results.ai_insights.update(modification)
                
                # Process with review capability
                if AICapability.CODE_REVIEW in self.capabilities:
                    review = await self._process_with_review(ast, context)
                    results.ai_insights.update(review)
                
                # Process with learning capability
                if AICapability.LEARNING in self.capabilities:
                    learning = await self._process_with_learning(ast, context)
                    results.learned_patterns.extend(learning)
                
                return results
            except Exception as e:
                log(f"Error in JSON AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )

    async def _process_with_understanding(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code understanding capability."""
        understanding = {}
        
        # Analyze structure
        understanding["structure"] = {
            "type": ast.get("type"),
            "depth": ast.get("metadata", {}).get("max_depth", 0),
            "child_count": len(ast.get("children", [])),
            "schema_type": ast.get("schema_type")
        }
        
        # Analyze patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze naming conventions
        understanding["naming"] = await self._analyze_naming_conventions(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with code generation capability."""
        suggestions = []
        
        # Generate schema suggestions
        if schema_suggestions := await self._generate_schema_suggestions(ast):
            suggestions.extend(schema_suggestions)
        
        # Generate structure suggestions
        if structure_suggestions := await self._generate_structure_suggestions(ast):
            suggestions.extend(structure_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code modification capability."""
        modifications = {}
        
        # Suggest structure improvements
        if improvements := await self._suggest_structure_improvements(ast):
            modifications["structure_improvements"] = improvements
        
        # Suggest naming improvements
        if naming := await self._suggest_naming_improvements(ast):
            modifications["naming_improvements"] = naming
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code review capability."""
        review = {}
        
        # Review structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review patterns
        if pattern_review := await self._review_patterns(ast):
            review["patterns"] = pattern_review
        
        return review

    async def _process_with_learning(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process with learning capability."""
        patterns = []
        
        # Learn structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn naming patterns
        if naming_patterns := await self._learn_naming_patterns(ast):
            patterns.extend(naming_patterns)
        
        return patterns

    async def cleanup(self):
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
            log("JSON parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up JSON parser: {e}", level="error") 