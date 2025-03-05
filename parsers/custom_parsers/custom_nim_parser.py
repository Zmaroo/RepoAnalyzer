"""Custom parser for Nim with enhanced documentation and pattern extraction features."""

from .base_imports import *

class NimParser(BaseParser, CustomParserMixin):
    """Parser for Nim files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "nim", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.patterns = self._compile_patterns(NIM_PATTERNS)
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("Nim parser initialization"):
                    await self._initialize_cache(self.language_id)
                    self._initialized = True
                    log("Nim parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing Nim parser: {e}", level="error")
                raise
        return True

    async def cleanup(self):
        """Clean up parser resources."""
        try:
            await self._cleanup_cache()
            log("Nim parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up Nim parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> NimNodeDict:
        """Create a standardized Nim AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "name": kwargs.get("name"),
            "parameters": kwargs.get("parameters", []),
            "return_type": kwargs.get("return_type")
        }

    def _process_parameters(self, params_str: str) -> List[Dict]:
        """Process procedure parameters into parameter nodes."""
        if not params_str.strip():
            return []
        
        param_nodes = []
        params = [p.strip() for p in params_str.split(',')]
        for param in params:
            if match := self.patterns['parameter'].match(param):
                param_nodes.append(
                    NIM_PATTERNS[PatternCategory.SEMANTICS]['parameter'].extract(match)
                )
        return param_nodes

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Nim content into AST structure."""
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(operation_name="Nim parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                task = asyncio.create_task(self._parse_content(source_code))
                self._pending_tasks.add(task)
                try:
                    return await task
                finally:
                    self._pending_tasks.remove(task)
                
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error parsing Nim content: {e}", level="error")
                return self._create_node(
                    "module",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                ).__dict__

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal method to parse Nim content synchronously."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "module",
            [0, 0],
            [len(lines) - 1, len(lines[-1]) if lines else 0]
        )

        current_doc = []
        
        for i, line in enumerate(lines):
            line_start = [i, 0]
            line_end = [i, len(line)]
            
            line = line.strip()
            if not line:
                continue

            # Process documentation
            if doc_match := self.patterns['docstring'].match(line):
                node = self._create_node(
                    "docstring",
                    line_start,
                    line_end,
                    **NIM_PATTERNS[PatternCategory.DOCUMENTATION]['docstring'].extract(doc_match)
                )
                current_doc.append(node)
                continue

            # Process procedures
            if proc_match := self.patterns['proc'].match(line):
                node = self._create_node(
                    "proc",
                    line_start,
                    line_end,
                    **NIM_PATTERNS[PatternCategory.SYNTAX]['proc'].extract(proc_match)
                )
                node.metadata["parameters"] = self._process_parameters(node.metadata.get("parameters", ""))
                if current_doc:
                    node.metadata["documentation"] = current_doc
                    current_doc = []
                ast.children.append(node)
                continue

            # Process other patterns
            for pattern_name, category in [
                ('type', PatternCategory.SYNTAX),
                ('import', PatternCategory.STRUCTURE),
                ('variable', PatternCategory.SEMANTICS)
            ]:
                if match := self.patterns[pattern_name].match(line):
                    node = self._create_node(
                        pattern_name,
                        line_start,
                        line_end,
                        **NIM_PATTERNS[category][pattern_name].extract(match)
                    )
                    if current_doc:
                        node.metadata["documentation"] = current_doc
                        current_doc = []
                    ast.children.append(node)
                    break

        # Add any remaining documentation
        if current_doc:
            ast.metadata["trailing_documentation"] = current_doc

        return ast.__dict__

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """Extract code patterns from Nim files for repository learning."""
        if not self._initialized:
            await self.initialize()

        patterns = []
        
        async with AsyncErrorBoundary(operation_name="Nim pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
            try:
                # Parse the source first to get a structured representation
                ast = await self._parse_source(source_code)
                
                # Extract patterns asynchronously
                task = asyncio.create_task(self._extract_all_patterns(ast))
                self._pending_tasks.add(task)
                try:
                    patterns = await task
                finally:
                    self._pending_tasks.remove(task)
                    
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error extracting Nim patterns: {e}", level="error")
                
        return patterns

    def _extract_all_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all patterns from the AST synchronously."""
        patterns = []
        
        # Extract procedure patterns
        proc_patterns = self._extract_proc_patterns(ast)
        for proc in proc_patterns:
            patterns.append({
                'name': f'nim_proc_{proc["name"]}',
                'content': proc["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'type': 'nim_proc',
                    'name': proc["name"],
                    'parameters': proc.get("parameters", []),
                    'return_type': proc.get("return_type")
                }
            })
        
        # Extract type patterns
        type_patterns = self._extract_type_patterns(ast)
        for type_pattern in type_patterns:
            patterns.append({
                'name': f'nim_type_{type_pattern["name"]}',
                'content': type_pattern["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'nim_type',
                    'name': type_pattern["name"]
                }
            })
            
        # Extract variable patterns and naming conventions
        var_patterns, naming_conventions = self._extract_variable_patterns(ast)
        
        for var_pattern in var_patterns:
            patterns.append({
                'name': f'nim_variable_{var_pattern["kind"]}',
                'content': var_pattern["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.8,
                'metadata': {
                    'type': 'nim_variable',
                    'kind': var_pattern["kind"],
                    'examples': var_pattern.get("examples", [])
                }
            })
            
        # Add naming convention patterns
        for convention in naming_conventions:
            patterns.append({
                'name': f'nim_naming_convention_{convention["name"]}',
                'content': convention["content"],
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'naming_convention',
                    'convention': convention["name"],
                    'examples': convention.get("examples", [])
                }
            })
            
        # Extract module structure patterns
        structure_patterns = self._extract_structure_patterns(ast)
        for structure in structure_patterns:
            patterns.append({
                'name': f'nim_structure_{structure["type"]}',
                'content': structure["content"],
                'pattern_type': PatternType.MODULE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'type': 'module_structure',
                    'structure_type': structure["type"],
                    'elements': structure.get("elements", [])
                }
            })
            
        return patterns
        
    def _extract_proc_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract procedure patterns from the AST."""
        procs = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'proc':
                proc_name = node.get('name', '')
                parameters = node.get('metadata', {}).get('parameters', [])
                return_type = node.get('return_type', '')
                
                # Format parameters for display
                param_strs = []
                for param in parameters:
                    param_type = param.get('value_type', '')
                    if param_type:
                        param_strs.append(f"{param.get('name', '')}: {param_type}")
                    else:
                        param_strs.append(param.get('name', ''))
                
                # Create procedure pattern
                if proc_name:
                    procs.append({
                        'name': proc_name,
                        'content': f"proc {proc_name}({', '.join(param_strs)}) {f': {return_type}' if return_type else ''}",
                        'parameters': parameters,
                        'return_type': return_type
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return procs
        
    def _extract_type_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract type patterns from the AST."""
        types = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'type':
                type_name = node.get('name', '')
                
                if type_name:
                    types.append({
                        'name': type_name,
                        'content': f"type {type_name}"
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return types
        
    def _extract_variable_patterns(self, ast: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract variable patterns and naming conventions from the AST."""
        variables = {}
        names = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'variable':
                var_kind = node.get('kind', '')
                var_name = node.get('name', '')
                var_type = node.get('value_type', '')
                var_value = node.get('value', '')
                
                if var_kind and var_name:
                    # Track the variable
                    if var_kind not in variables:
                        variables[var_kind] = []
                    
                    variables[var_kind].append({
                        'name': var_name,
                        'type': var_type,
                        'value': var_value
                    })
                    
                    # Track the name for naming convention analysis
                    names.append(var_name)
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        
        # Create variable patterns by kind
        var_patterns = []
        for kind, vars_list in variables.items():
            if vars_list:
                var_patterns.append({
                    'kind': kind,
                    'content': f"{kind} examples: " + ", ".join(v['name'] for v in vars_list[:3]),
                    'examples': vars_list[:5]
                })
        
        # Analyze naming conventions
        naming_conventions = self._analyze_naming_conventions(names)
        
        return var_patterns, naming_conventions
        
    def _analyze_naming_conventions(self, names: List[str]) -> List[Dict[str, Any]]:
        """Analyze naming conventions from a list of names."""
        if not names:
            return []
            
        convention_patterns = {
            'camelCase': r'^[a-z][a-zA-Z0-9]*$',
            'snake_case': r'^[a-z][a-z0-9_]*$',
            'PascalCase': r'^[A-Z][a-zA-Z0-9]*$',
            'UPPER_CASE': r'^[A-Z][A-Z0-9_]*$'
        }
        
        # Count occurrences of each convention
        conventions = {}
        for name in names:
            for conv_name, pattern in convention_patterns.items():
                if re.match(pattern, name):
                    if conv_name == 'camelCase' and not any(c.isupper() for c in name):
                        continue  # Skip if it doesn't have any uppercase chars
                    if conv_name == 'snake_case' and '_' not in name:
                        continue  # Skip if it doesn't have underscores
                    if conv_name == 'UPPER_CASE' and '_' not in name:
                        continue  # Skip if it doesn't have underscores
                        
                    conventions[conv_name] = conventions.get(conv_name, 0) + 1
        
        # Create patterns for dominant conventions
        results = []
        if conventions:
            dominant_convention = max(conventions.items(), key=lambda x: x[1])
            
            # Only include if we have enough examples
            if dominant_convention[1] >= 2:
                # Get examples of this convention
                examples = [name for name in names if re.match(convention_patterns[dominant_convention[0]], name)][:5]
                
                results.append({
                    'name': dominant_convention[0],
                    'content': f"Naming convention: {dominant_convention[0]} (e.g., {', '.join(examples)})",
                    'examples': examples
                })
                
        return results
        
    def _extract_structure_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract module structure patterns from the AST."""
        # Count different types of top-level nodes
        type_counts = Counter()
        imports = []
        
        for child in ast.get('children', []):
            if isinstance(child, dict):
                node_type = child.get('type')
                if node_type:
                    type_counts[node_type] += 1
                    
                # Collect imports
                if node_type == 'import':
                    modules = child.get('modules', [])
                    if modules:
                        imports.extend(modules)
        
        patterns = []
        
        # Create a module structure pattern
        if type_counts:
            structure_elements = [f"{count} {node_type}{'s' if count > 1 else ''}" 
                                 for node_type, count in type_counts.most_common()]
            
            patterns.append({
                'type': 'module_composition',
                'content': f"Module structure: {', '.join(structure_elements)}",
                'elements': [{'type': t, 'count': c} for t, c in type_counts.items()]
            })
        
        # Create an import pattern if applicable
        if imports:
            patterns.append({
                'type': 'imports',
                'content': f"Module imports: {', '.join(imports[:5])}",
                'elements': imports
            })
            
        return patterns