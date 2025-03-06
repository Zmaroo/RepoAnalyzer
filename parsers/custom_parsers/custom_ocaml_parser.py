"""
Custom OCaml parsers with enhanced pattern extraction capabilities.

This module implements custom parsers for OCaml source files because we do not have
Tree-sitter language support for OCaml. Two kinds of source files are supported:
  - OCaml implementation files (.ml)
  - OCaml interface files (.mli)

Each parser extracts top-level declarations using regular expressions and converts the
source into a simplified custom AST with metadata (e.g. approximate byte positions,
document positions, and a top-level documentation comment if present).

NOTE:
  - This parser is intentionally a lightweight implementation meant for database ingestion
    and deep code base understanding. You can refine it over time to capture more detail.
  - Integrate this module with your main language parsing entry point so that when a file
    ends with .ml or .mli the corresponding function is called.

This module implements custom parsers for OCaml source files using a class-based structure.
Standalone parsing functions have been removed in favor of the classes below.
"""

from .base_imports import *
import re
from parsers.pattern_processor import pattern_processor
from parsers.query_patterns.ocaml_interface import OCAML_INTERFACE_PATTERNS
from parsers.query_patterns.ocaml import OCAML_PATTERNS

def compute_offset(lines, line_no, col):
    """
    Compute the byte offset for a given (line, col) pair.
    We assume that each line is terminated by a single newline character.
    """
    return sum(len(lines[i]) + 1 for i in range(line_no)) + col

class OcamlParser(BaseParser, CustomParserMixin):
    """Parser for OCaml files with enhanced pattern extraction capabilities."""
    
    def __init__(self, language_id: str = "ocaml", file_type: Optional[FileType] = None):
        BaseParser.__init__(self, language_id, file_type or FileType.CODE, parser_type=ParserType.CUSTOM)
        CustomParserMixin.__init__(self)
        self.is_interface = language_id == "ocaml_interface"
        self._initialized = False
        self._pending_tasks: Set[asyncio.Future] = set()
        self.capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.LEARNING
        }
        register_shutdown_handler(self.cleanup)
    
    @handle_async_errors(error_types=(Exception,))
    async def initialize(self) -> bool:
        """Initialize parser resources."""
        if not self._initialized:
            try:
                async with AsyncErrorBoundary("OCaml parser initialization"):
                    await self._initialize_cache(self.language_id)
                    await self._load_patterns()
                    
                    # Initialize AI processor
                    self._ai_processor = AIPatternProcessor(self)
                    await self._ai_processor.initialize()
                    
                    # Initialize pattern processor
                    self._pattern_processor = await PatternProcessor.create()
                    
                    self._initialized = True
                    log("OCaml parser initialized", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing OCaml parser: {e}", level="error")
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
            log("OCaml parser cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up OCaml parser: {e}", level="error")

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> OcamlNodeDict:
        """Create a standardized OCaml AST node using the shared helper."""
        node_dict = super()._create_node(node_type, start_point, end_point, **kwargs)
        return {
            **node_dict,
            "name": kwargs.get("name"),
            "parameters": kwargs.get("parameters", []),
            "return_type": kwargs.get("return_type")
        }

    @handle_errors(error_types=(ParsingError,))
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse OCaml content into AST structure.
        
        This method supports AST caching through the BaseParser.parse() method.
        Cache checks are handled at the BaseParser level, so this method is only called
        on cache misses or when we need to generate a fresh AST.
        """
        if not self._initialized:
            await self.initialize()

        async with AsyncErrorBoundary(operation_name="OCaml parsing", error_types=(ParsingError,), severity=ErrorSeverity.ERROR):
            try:
                task = asyncio.create_task(self._parse_content(source_code))
                self._pending_tasks.add(task)
                try:
                    return await task
                finally:
                    self._pending_tasks.remove(task)
                
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                log(f"Error parsing OCaml content: {e}", level="error")
                return self._create_node(
                    "module",
                    [0, 0],
                    [0, 0],
                    error=str(e),
                    children=[]
                )

    def _parse_content(self, source_code: str) -> Dict[str, Any]:
        """Internal method to parse OCaml content synchronously."""
        lines = source_code.splitlines()
        ast = self._create_node(
            "module",
            [0, 0],
            [len(lines) - 1, len(lines[-1]) if lines else 0]
        )

        current_doc = []
        patterns = OCAML_INTERFACE_PATTERNS if self.is_interface else OCAML_PATTERNS
        
        for i, line in enumerate(lines):
            line_start = [i, 0]
            line_end = [i, len(line)]
            
            line = line.strip()
            if not line:
                continue

            # Process documentation
            if doc_match := self.patterns['doc_comment'].match(line):
                node = self._create_node(
                    "doc_comment",
                    line_start,
                    line_end,
                    **self.patterns['doc_comment'].extract(doc_match)
                )
                current_doc.append(node)
                continue

            # Process declarations
            for category in ["syntax", "structure", "semantics"]:
                for pattern_name, pattern_info in patterns[category].items():
                    if match := self.patterns[pattern_name].match(line):
                        node = self._create_node(
                            pattern_name,
                            line_start,
                            line_end,
                            **self.patterns[pattern_name].extract(match)
                        )
                        if current_doc:
                            node.metadata["documentation"] = current_doc
                            current_doc = []
                        ast.children.append(node)
                        break

        # Add any remaining documentation
        if current_doc:
            ast.metadata["trailing_documentation"] = current_doc

        return ast

    @handle_errors(error_types=(ProcessingError,))
    async def extract_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """
        Extract code patterns from OCaml files for repository learning.
        
        Args:
            source_code: The content of the OCaml file
            
        Returns:
            List of extracted patterns with metadata
        """
        if not self._initialized:
            await self.initialize()

        patterns = []
        
        async with AsyncErrorBoundary(operation_name="OCaml pattern extraction", error_types=(ProcessingError,), severity=ErrorSeverity.ERROR):
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
                log(f"Error extracting OCaml patterns: {e}", level="error")
                
        return patterns

    def _extract_all_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all patterns from the AST synchronously."""
        patterns = []
        
        # Extract let binding patterns
        let_patterns = self._extract_let_binding_patterns(ast)
        for binding in let_patterns:
            patterns.append({
                'name': f'ocaml_binding_{binding["name"]}',
                'content': binding["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'type': 'let_binding',
                    'name': binding["name"],
                    'is_recursive': binding.get("is_recursive", False)
                }
            })
        
        # Extract type patterns
        type_patterns = self._extract_type_patterns(ast)
        for type_pattern in type_patterns:
            patterns.append({
                'name': f'ocaml_type_{type_pattern["name"]}',
                'content': type_pattern["content"],
                'pattern_type': PatternType.CODE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'ocaml_type',
                    'name': type_pattern["name"]
                }
            })
            
        # Extract module patterns
        module_patterns = self._extract_module_patterns(ast)
        for module_pattern in module_patterns:
            patterns.append({
                'name': f'ocaml_module_{module_pattern["name"]}',
                'content': module_pattern["content"],
                'pattern_type': PatternType.MODULE_STRUCTURE,
                'language': self.language_id,
                'confidence': 0.9,
                'metadata': {
                    'type': 'ocaml_module',
                    'name': module_pattern["name"],
                    'elements': module_pattern.get("elements", [])
                }
            })
            
        # Extract naming convention patterns
        naming_patterns = self._extract_naming_convention_patterns(ast)
        for naming in naming_patterns:
            patterns.append({
                'name': f'ocaml_naming_{naming["convention"]}',
                'content': naming["content"],
                'pattern_type': PatternType.NAMING_CONVENTION,
                'language': self.language_id,
                'confidence': 0.85,
                'metadata': {
                    'type': 'naming_convention',
                    'convention': naming["convention"],
                    'examples': naming.get("examples", [])
                }
            })
            
        # Extract documentation patterns
        doc_patterns = self._extract_documentation_patterns(ast)
        for doc in doc_patterns:
            patterns.append({
                'name': f'ocaml_doc_{doc["type"]}',
                'content': doc["content"],
                'pattern_type': PatternType.DOCUMENTATION,
                'language': self.language_id,
                'confidence': 0.95,
                'metadata': {
                    'type': 'documentation',
                    'doc_type': doc["type"],
                    'examples': doc.get("examples", [])
                }
            })
            
        return patterns
        
    def _extract_let_binding_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract let binding patterns from the AST."""
        bindings = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'let_binding':
                binding_name = self._extract_binding_name(node.get('name', ''))
                is_recursive = 'rec' in node.get('name', '')
                
                if binding_name:
                    bindings.append({
                        'name': binding_name,
                        'content': node.get('name', ''),
                        'is_recursive': is_recursive
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return bindings
        
    def _extract_binding_name(self, binding_text: str) -> str:
        """Extract the name from a let binding text."""
        # Match 'let name' or 'let rec name'
        match = re.search(r'let\s+(?:rec\s+)?(\w+)', binding_text)
        if match:
            return match.group(1)
        return ""
        
    def _extract_type_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract type patterns from the AST."""
        types = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'type_definition':
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
        
    def _extract_module_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract module patterns from the AST."""
        modules = []
        
        def process_node(node):
            if isinstance(node, dict) and node.get('type') == 'module_declaration':
                module_name = node.get('name', '')
                
                if module_name:
                    modules.append({
                        'name': module_name,
                        'content': f"module {module_name}",
                        'elements': [child.get('type') for child in node.get('children', [])]
                    })
            
            # Process children recursively
            if isinstance(node, dict):
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return modules
        
    def _extract_naming_convention_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract naming convention patterns from the AST."""
        # Collect different name types
        values = []
        types = []
        modules = []
        
        def process_node(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                name = node.get('name', '')
                
                if node_type == 'let_binding' and name:
                    binding_name = self._extract_binding_name(name)
                    if binding_name:
                        values.append(binding_name)
                elif node_type == 'type_definition' and name:
                    types.append(name)
                elif node_type == 'module_declaration' and name:
                    modules.append(name)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        
        # Analyze naming conventions
        patterns = []
        
        # Value naming conventions
        if values:
            value_convention = self._analyze_naming_convention(values)
            if value_convention:
                patterns.append({
                    'convention': f"value_{value_convention}",
                    'content': f"Value naming convention: {value_convention} (e.g., {', '.join(values[:3])})",
                    'examples': values[:5]
                })
        
        # Type naming conventions
        if types:
            type_convention = self._analyze_naming_convention(types)
            if type_convention:
                patterns.append({
                    'convention': f"type_{type_convention}",
                    'content': f"Type naming convention: {type_convention} (e.g., {', '.join(types[:3])})",
                    'examples': types[:5]
                })
        
        # Module naming conventions
        if modules:
            module_convention = self._analyze_naming_convention(modules)
            if module_convention:
                patterns.append({
                    'convention': f"module_{module_convention}",
                    'content': f"Module naming convention: {module_convention} (e.g., {', '.join(modules[:3])})",
                    'examples': modules[:5]
                })
                
        return patterns
        
    def _analyze_naming_convention(self, names: List[str]) -> Optional[str]:
        """Analyze naming convention from a list of names."""
        if not names:
            return None
            
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
        
        # Return the dominant convention if we have enough examples
        if conventions:
            dominant_convention = max(conventions.items(), key=lambda x: x[1])
            if dominant_convention[1] >= 2:
                return dominant_convention[0]
                
        return None
        
    def _extract_documentation_patterns(self, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract documentation patterns from the AST."""
        patterns = []
        
        def process_node(node):
            if isinstance(node, dict):
                # Process node documentation
                docs = node.get('metadata', {}).get('documentation', [])
                if docs:
                    doc_type = node.get('type', 'unknown')
                    patterns.append({
                        'type': f"{doc_type}_doc",
                        'content': "\n".join(d.get('content', '') for d in docs),
                        'examples': [d.get('content', '') for d in docs]
                    })
                
                # Process trailing documentation
                trailing_docs = node.get('metadata', {}).get('trailing_documentation', [])
                if trailing_docs:
                    patterns.append({
                        'type': 'trailing_doc',
                        'content': "\n".join(d.get('content', '') for d in trailing_docs),
                        'examples': [d.get('content', '') for d in trailing_docs]
                    })
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
                
        process_node(ast)
        return patterns

    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """Process OCaml code with AI assistance."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary("OCaml AI processing"):
            try:
                # Parse source first
                ast = await self._parse_source(source_code)
                if not ast:
                    return AIProcessingResult(
                        success=False,
                        response="Failed to parse OCaml code"
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
                log(f"Error in OCaml AI processing: {e}", level="error")
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
        
        # Analyze code structure
        understanding["structure"] = {
            "let_bindings": self._extract_let_binding_patterns(ast),
            "types": self._extract_type_patterns(ast),
            "modules": self._extract_module_patterns(ast)
        }
        
        # Analyze code patterns
        understanding["patterns"] = await self._analyze_patterns(ast, context)
        
        # Analyze code style
        understanding["style"] = await self._analyze_code_style(ast)
        
        return understanding

    async def _process_with_generation(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[str]:
        """Process with code generation capability."""
        suggestions = []
        
        # Generate binding suggestions
        if binding_suggestions := await self._generate_binding_suggestions(ast):
            suggestions.extend(binding_suggestions)
        
        # Generate type suggestions
        if type_suggestions := await self._generate_type_suggestions(ast):
            suggestions.extend(type_suggestions)
        
        # Generate module suggestions
        if module_suggestions := await self._generate_module_suggestions(ast):
            suggestions.extend(module_suggestions)
        
        return suggestions

    async def _process_with_modification(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code modification capability."""
        modifications = {}
        
        # Suggest code improvements
        if improvements := await self._suggest_code_improvements(ast):
            modifications["code_improvements"] = improvements
        
        # Suggest refactoring opportunities
        if refactoring := await self._suggest_refactoring(ast):
            modifications["refactoring"] = refactoring
        
        # Suggest optimization opportunities
        if optimization := await self._suggest_optimization(ast):
            modifications["optimization"] = optimization
        
        return modifications

    async def _process_with_review(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Process with code review capability."""
        review = {}
        
        # Review code structure
        if structure_review := await self._review_structure(ast):
            review["structure"] = structure_review
        
        # Review code style
        if style_review := await self._review_style(ast):
            review["style"] = style_review
        
        # Review module organization
        if module_review := await self._review_modules(ast):
            review["modules"] = module_review
        
        return review

    async def _process_with_learning(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> List[Dict[str, Any]]:
        """Process with learning capability."""
        patterns = []
        
        # Learn code structure patterns
        if structure_patterns := await self._learn_structure_patterns(ast):
            patterns.extend(structure_patterns)
        
        # Learn coding style patterns
        if style_patterns := await self._learn_style_patterns(ast):
            patterns.extend(style_patterns)
        
        # Learn module patterns
        if module_patterns := await self._learn_module_patterns(ast):
            patterns.extend(module_patterns)
        
        return patterns

    async def _analyze_patterns(
        self,
        ast: Dict[str, Any],
        context: AIContext
    ) -> Dict[str, Any]:
        """Analyze patterns in the OCaml code."""
        patterns = {}
        
        # Analyze binding patterns
        patterns["binding_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.STRUCTURE,
            context
        )
        
        # Analyze type patterns
        patterns["type_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.SYNTAX,
            context
        )
        
        # Analyze module patterns
        patterns["module_patterns"] = await self._pattern_processor.analyze_patterns(
            ast,
            PatternCategory.MODULE,
            context
        )
        
        return patterns

    async def _analyze_code_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze code style."""
        style = {}
        
        # Analyze naming conventions
        style["naming_conventions"] = self._analyze_naming_convention_patterns(ast)
        
        # Analyze binding style
        style["binding_style"] = self._analyze_binding_style(ast)
        
        # Analyze module style
        style["module_style"] = self._analyze_module_style(ast)
        
        return style

    async def _generate_binding_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate binding suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing bindings
        bindings = self._extract_let_binding_patterns(ast)
        
        # Suggest common missing bindings
        common_bindings = {
            "init": "Initialize module resources",
            "cleanup": "Clean up module resources",
            "create": "Create a new instance",
            "process": "Process input data"
        }
        
        for name, description in common_bindings.items():
            if not any(b["name"] == name for b in bindings):
                suggestions.append(f"Add binding '{name}' to {description}")
        
        return suggestions

    async def _generate_type_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate type suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing types
        types = self._extract_type_patterns(ast)
        
        # Suggest common missing types
        common_types = {
            "config": "Configuration type",
            "error": "Error type",
            "result": "Result type",
            "state": "State type"
        }
        
        for name, description in common_types.items():
            if not any(t["name"] == name for t in types):
                suggestions.append(f"Add type '{name}' for {description}")
        
        return suggestions

    async def _generate_module_suggestions(
        self,
        ast: Dict[str, Any]
    ) -> List[str]:
        """Generate module suggestions based on the AST."""
        suggestions = []
        
        # Analyze existing modules
        modules = self._extract_module_patterns(ast)
        
        # Suggest common missing modules
        common_modules = {
            "Types": "Type definitions",
            "Utils": "Utility functions",
            "Error": "Error handling",
            "State": "State management"
        }
        
        for name, description in common_modules.items():
            if not any(m["name"] == name for m in modules):
                suggestions.append(f"Add module '{name}' for {description}")
        
        return suggestions

    async def _suggest_code_improvements(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest code improvements based on the AST."""
        improvements = {}
        
        # Analyze bindings for improvements
        bindings = self._extract_let_binding_patterns(ast)
        binding_improvements = []
        for binding in bindings:
            if binding.get("is_recursive", False) and not binding.get("has_base_case", False):
                binding_improvements.append(f"Add base case to recursive binding '{binding['name']}'")
        if binding_improvements:
            improvements["bindings"] = binding_improvements
        
        # Analyze types for improvements
        types = self._extract_type_patterns(ast)
        type_improvements = []
        for type_def in types:
            if not type_def.get("documentation"):
                type_improvements.append(f"Add documentation to type '{type_def['name']}'")
        if type_improvements:
            improvements["types"] = type_improvements
        
        return improvements

    async def _suggest_refactoring(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest refactoring opportunities based on the AST."""
        refactoring = {}
        
        # Analyze module structure for refactoring
        modules = self._extract_module_patterns(ast)
        module_refactoring = []
        for module in modules:
            if len(module.get("elements", [])) > 10:
                module_refactoring.append(f"Consider splitting module '{module['name']}' into smaller modules")
        if module_refactoring:
            refactoring["modules"] = module_refactoring
        
        return refactoring

    async def _suggest_optimization(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest optimization opportunities based on the AST."""
        optimization = {}
        
        # Analyze bindings for optimization
        bindings = self._extract_let_binding_patterns(ast)
        binding_optimization = []
        for binding in bindings:
            if binding.get("complexity", "O(n)") == "O(n^2)":
                binding_optimization.append(f"Consider optimizing binding '{binding['name']}' to reduce complexity")
        if binding_optimization:
            optimization["bindings"] = binding_optimization
        
        return optimization

    async def _review_structure(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review code structure based on the AST."""
        review = {}
        
        # Review module structure
        modules = self._extract_module_patterns(ast)
        module_review = []
        for module in modules:
            module_review.append({
                "name": module["name"],
                "element_count": len(module.get("elements", [])),
                "has_interface": module.get("has_interface", False)
            })
        if module_review:
            review["modules"] = module_review
        
        return review

    async def _review_style(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review code style based on the AST."""
        review = {}
        
        # Review naming conventions
        naming = self._analyze_naming_convention_patterns(ast)
        if naming:
            review["naming"] = naming
        
        # Review documentation style
        docs = self._extract_documentation_patterns(ast)
        if docs:
            review["documentation"] = docs
        
        return review

    async def _review_modules(
        self,
        ast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Review module organization based on the AST."""
        review = {}
        
        # Review module dependencies
        modules = self._extract_module_patterns(ast)
        dependencies = {}
        for module in modules:
            dependencies[module["name"]] = module.get("dependencies", [])
        if dependencies:
            review["dependencies"] = dependencies
        
        return review 