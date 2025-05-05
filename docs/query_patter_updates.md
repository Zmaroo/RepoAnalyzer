# Query Pattern Updates for RepoAnalyzer

This document provides the essential updates needed for all query pattern files in RepoAnalyzer to ensure proper integration with both custom parsers and tree-sitter parsers.

## 1. System Architecture Overview

RepoAnalyzer's query pattern system is organized into several key components that work together to provide pattern matching capabilities. The system is primarily focused on tree-sitter patterns while maintaining support for custom parsers.

### Core Components

#### Base Pattern Infrastructure (`base_patterns.py`)

- Provides abstract base classes used by all pattern types
- Core classes:
  - `BasePattern`: Abstract base for all patterns
  - `BaseAdaptivePattern`: Base for patterns that can learn and adapt
  - `BaseResilientPattern`: Base for patterns with error recovery
  - `BasePatternContext`: Context information for pattern matching
  - `BasePatternPerformanceMetrics`: Performance tracking
  - `BaseCrossProjectPatternLearner`: Base for pattern learning

#### Tree-Sitter Pattern Implementation (`enhanced_patterns.py`)

- Implements specialized tree-sitter pattern classes
- Key classes:
  - `TreeSitterPattern`: Core tree-sitter pattern implementation
  - `TreeSitterAdaptivePattern`: Adaptive tree-sitter patterns
  - `TreeSitterResilientPattern`: Resilient patterns with recovery
  - `TreeSitterPatternContext`: Tree-sitter specific context
  - `TreeSitterCrossProjectPatternLearner`: Cross-project learning

#### Common Pattern Infrastructure (`common.py`)

- Core tree-sitter pattern infrastructure and utilities
- Key functions:
  - `process_tree_sitter_pattern()`: Pattern processing
  - `validate_tree_sitter_pattern()`: Pattern validation
  - `create_tree_sitter_context()`: Context creation
  - `update_common_pattern_metrics()`: Metrics tracking
- Provides common pattern definitions and relationships

#### Learning Strategies (`learning_strategies.py`)

- Pattern learning and improvement strategies
- Available strategies:
  - `NodePatternImprovement`: Node structure improvements
  - `CaptureOptimization`: Capture usage optimization
  - `PredicateRefinement`: Predicate refinement
  - `PatternGeneralization`: Pattern generalization

#### Recovery Strategies (`recovery_strategies.py`)

- Error recovery strategies for resilient patterns
- Available strategies:
  - `FallbackPatternStrategy`: Fallback pattern usage
  - `RegexFallbackStrategy`: Regex pattern fallback
  - `PartialMatchStrategy`: Partial code matching

#### Tree-Sitter Utilities (`tree_sitter_utils.py`)

- Utility functions for tree-sitter operations
- Key functions:
  - `execute_tree_sitter_query()`: Query execution
  - `extract_captures()`: Capture processing
  - `regex_matches()`: Regex fallback matching
  - `count_nodes()`: AST node counting

### Advanced Tree-sitter Integration

#### AST Analysis Pipeline

```python
# Example AST analysis
def _convert_tree_to_dict(node) -> Dict[str, Any]:
    result = {
        "type": node.type,
        "start_point": node.start_point,
        "end_point": node.end_point
    }
    if len(node.children) > 0:
        result["children"] = [_convert_tree_to_dict(child) for child in node.children]
    return result
```

#### Node Tracking System

- Comprehensive node tracking
- Parent-child relationships
- Node type statistics
- Depth calculation
- Position tracking

#### Performance Optimization

- Query complexity analysis
- Execution strategy selection
- Match limiting
- Timeout handling
- Caching integration

#### Error Recovery Strategies

- Multiple pattern variants
- Fallback patterns
- Partial matching
- Regex fallbacks
- Error context preservation

### Pattern Learning & Adaptation

#### AI-Assisted Learning

```python
# Example AI-assisted pattern learning
async def learn_from_project(self, project_path: str):
    # AI processing
    ai_result = await self._ai_processor.process_with_ai(
        source_code="",
        context=ai_context
    )
    
    # Cross-project learning
    project_patterns = await self._extract_project_patterns(project_path)
    
    # Feature-based learning
    python_patterns = await self._learn_patterns_from_features(features)
```

#### Cross-Repository Learning Implementation

```python
class TreeSitterCrossProjectPatternLearner:
    async def learn_from_repository(
        self,
        repository_path: str,
        language_id: str,
        patterns: List[Union[TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern]] = None,
        sample_limit: int = 100
    ) -> Dict[str, Any]:
        # Find relevant files
        language_files = await self._find_language_files(
            repository_path, language_id, sample_limit
        )
        
        # Analyze files for insights
        insights = await self._analyze_files(
            language_files, language_id, patterns
        )
        
        # Improve patterns
        for pattern in patterns:
            improved_pattern = await self._improve_pattern(
                pattern, insights[pattern_key], language_id
            )
```

#### Pattern Metrics & Analytics

```python
PATTERN_METRICS = {
    "class": PatternPerformanceMetrics(),
    "function": PatternPerformanceMetrics(),
    "module": PatternPerformanceMetrics(),
    "decorator": PatternPerformanceMetrics(),
    "import": PatternPerformanceMetrics()
}
```

### Pattern Processing Core Steps

1. **Initialize Pattern**:

   ```python
   await pattern.initialize()
   ```

2. **Create Context**:

   ```python
   context = await create_tree_sitter_context(
       file_path="example.py",
       code_structure=ast,
       parser_type=ParserType.TREE_SITTER
   )
   ```

3. **Process Pattern**:

   ```python
   matches = await process_tree_sitter_pattern(
       pattern=pattern,
       source_code=source_code,
       context=context
   )
   ```

4. **Handle Results**:

   ```python
   for match in matches:
       # Access captured nodes
       name = match["captures"]["function.name"][0]["text"]
       # Access extracted data
       function_data = pattern.extract(match)
   ```

### Pattern Learning Architecture

1. **Initialize Learner**:

   ```python
   learner = TreeSitterCrossProjectPatternLearner()
   await learner.initialize()
   ```

2. **Configure Learning Strategies**:

   ```python
   strategies = get_learning_strategies()
   enabled_strategies = [
       "node_pattern_improvement",
       "capture_optimization",
       "predicate_refinement",
       "pattern_generalization"
   ]
   ```

3. **Learn from Repository**:

   ```python
   results = await learner.learn_from_repository(
       repository_path="/path/to/repo",
       language_id="python",
       patterns=[pattern1, pattern2]
   )
   ```

4. **Apply Improvements**:

   ```python
   for pattern_name, improved in results["improvements"].items():
       # Validate improvement
       validation = await validate_tree_sitter_pattern(improved["pattern"])
       if validation.is_valid:
           # Apply improvement
           patterns[pattern_name].pattern = improved["pattern"]
   ```

### Pattern Recovery Pipeline

1. **Define Recovery Strategies**:

   ```python
   strategies = get_recovery_strategies()
   ```

2. **Create Resilient Pattern**:

   ```python
   resilient_pattern = TreeSitterResilientPattern(
       name="example",
       pattern="...",
       fallback_patterns=[
           "simpler_pattern_1",
           "simpler_pattern_2"
       ],
       regex_pattern=r"fallback_regex_pattern",
       recovery_config={
           "strategies": ["fallback_patterns", "regex_fallback", "partial_match"],
           "max_attempts": 3,
           "timeout": 5.0
       }
   )
   ```

3. **Process with Recovery**:

   ```python
   try:
       matches = await resilient_pattern.matches(source_code)
   except Exception as e:
       # Pattern will attempt recovery automatically
       pass
   ```

### Pattern Learning Results

1. **Initialize Learner**:

   ```python
   learner = TreeSitterCrossProjectPatternLearner()
   await learner.initialize()
   ```

2. **Configure Learning Strategies**:

   ```python
   strategies = get_learning_strategies()
   enabled_strategies = [
       "node_pattern_improvement",
       "capture_optimization",
       "predicate_refinement",
       "pattern_generalization"
   ]
   ```

3. **Learn from Repository**:

   ```python
   results = await learner.learn_from_repository(
       repository_path="/path/to/repo",
       language_id="python",
       patterns=[pattern1, pattern2]
   )
   ```

4. **Apply Improvements**:

   ```python
   for pattern_name, improved in results["improvements"].items():
       # Validate improvement
       validation = await validate_tree_sitter_pattern(improved["pattern"])
       if validation.is_valid:
           # Apply improvement
           patterns[pattern_name].pattern = improved["pattern"]
   ```

## 3. Pattern Development Guidelines and Standards

### Core Development Principles

1. **Pattern Organization**:
   - Keep related patterns in the same file
   - Group patterns by category and purpose
   - Use consistent naming conventions

2. **Performance Optimization**:
   - Use appropriate timeouts and match limits
   - Implement caching where beneficial
   - Monitor pattern metrics

3. **Error Handling**:
   - Always use try-except blocks
   - Implement appropriate recovery strategies
   - Log errors with context

4. **Testing**:
   - Include comprehensive test cases
   - Test with various input sizes
   - Validate pattern improvements

5. **Documentation**:
   - Document pattern purpose and usage
   - Include example matches
   - Document recovery strategies

### Implementation Best Practices

1. **Code Structure**:
   - Follow modular design principles
   - Maintain clear separation of concerns
   - Use consistent naming conventions

2. **Performance Considerations**:
   - Implement efficient caching strategies
   - Optimize query patterns
   - Monitor and tune resource usage

3. **Error Recovery**:
   - Implement graceful fallback mechanisms
   - Provide detailed error context
   - Maintain error recovery metrics

4. **Quality Assurance**:
   - Write comprehensive unit tests
   - Perform integration testing
   - Validate pattern behavior

5. **Maintenance**:
   - Keep documentation up-to-date
   - Monitor system health
   - Track performance metrics

## 4. Troubleshooting and Solutions

1. **Pattern Compilation Failures**:
   - Validate syntax before use
   - Use simpler patterns as fallbacks
   - Check language-specific syntax

2. **Performance Issues**:
   - Review and adjust timeouts
   - Optimize capture usage
   - Consider pattern complexity

3. **Recovery Failures**:
   - Implement multiple fallback strategies
   - Use regex patterns as last resort
   - Log recovery attempts

4. **Learning Issues**:
   - Validate learned patterns
   - Monitor confidence scores
   - Review learning metrics

## 5. Implementation and Deployment Tasks

- [ ] Import required modules
- [ ] Define pattern structure
- [ ] Implement error recovery
- [ ] Add test cases
- [ ] Configure learning strategies
- [ ] Add performance monitoring
- [ ] Document usage and examples
- [ ] Review best practices
- [ ] Test thoroughly
- [ ] Monitor in production
- [ ] Implement health checks
- [ ] Configure metrics collection
- [ ] Set up error tracking
- [ ] Enable pattern learning
- [ ] Configure cross-repo analysis
- [ ] Set up recovery strategies
- [ ] Configure performance optimization
- [ ] Implement context validation
- [ ] Set up health monitoring
- [ ] Configure error auditing
- [ ] Implement memory management
- [ ] Set up pattern validation

## 6. Tree-sitter Query System Reference

### `matches(node, predicate=None)`

Returns a list of tuples with (pattern_index, captures_dict):

```python
# Example return value from matches():
[
    (0, {"function.name": <Node type=identifier, start=10, end=23>}),
    (1, {"function.name": <Node type=identifier, start=45, end=58>})
]
```

### `captures(node, predicate=None)`

Returns a dictionary with capture names mapped to lists of nodes:

```python
# Example return value from captures():
{
    "function.name": [<Node type=identifier, start=10, end=23>, 
                     <Node type=identifier, start=45, end=58>]
}
```

### Important Node Properties

```python
node.type        # Type string (e.g., "identifier", "block")
node.text        # Source text 
node.start_byte  # Byte offset start
node.end_byte    # Byte offset end
node.start_point # (row, column) start
node.end_point   # (row, column) end
node.parent      # Parent node
node.children    # Child nodes list
```

## 7. Pattern Testing & Validation Support

### For Tree-Sitter Patterns

```python
# Validate a tree-sitter pattern
result = await pattern.validate(source_code)

# Test pattern with more details
test_result = await pattern.test(source_code)

# Validate pattern syntax
syntax_result = await pattern.validate_syntax()

# Validate against test cases
test_cases_result = await pattern.validate_against_test_cases()

# For adaptive patterns
adaptive_result = await adaptive_pattern.validate_and_adapt(source_code)

# For resilient patterns
resilient_result = await resilient_pattern.validate_with_recovery(source_code)
```

### For Custom Patterns

Add test cases for automated validation:

```python
"function_definition": AdaptivePattern(
    # Pattern definition...
    test_cases=[
        {
            "input": "def example_function(arg1, arg2):\n    return arg1 + arg2",
            "expected": {"name": "example_function", "params": ["arg1", "arg2"]}
        }
    ]
)
```

## 8. Learning & Adaptation

### Tree-Sitter Pattern Learning

```python
learner = TreeSitterCrossProjectPatternLearner()
await learner.initialize()
result = await learner.learn_from_repository("/path/to/repo", "python")
```

### Custom Pattern Learning

```python
learner = CommonPatternLearner()  # From common_custom.py
await learner.initialize()
patterns = await learner.learn_from_project("/path/to/project")
```

## 9. Common Integration Errors to Watch For

1. **Missing Context**: If you see error messages about missing context, ensure you're creating context with the correct function
2. **Pattern Not Defined**: Make sure you're importing from the correct pipeline (tree-sitter vs custom)
3. **Type Errors**: If you see errors about invalid types, ensure you're using the right pattern classes for your parser type
4. **Naming Conflicts**: Watch for confusion between `PatternContext` (custom) and tree-sitter contexts

## 10. Implementation Priority

1. Determine appropriate parser type for your language
2. Select the correct module imports based on parser type
3. Implement patterns using appropriate pattern classes
4. Use the correct processing and validation functions
5. Add test cases for validation
6. Optimize patterns based on parser-specific techniques

All query pattern files should implement updates based on their corresponding parser type to ensure proper integration with the parser architecture.

### Advanced Error Recovery System

#### Recovery Flow

```python
class TreeSitterResilientPattern:
    async def _try_recovery_strategies(
        self,
        source_code: str,
        original_errors: List[str]
    ) -> PatternValidationResult:
        # Track recovery attempt
        self.recovery_metrics["attempts"] += 1
        start_time = time.time()
        
        # Try each strategy in order
        for strategy_name in enabled_strategies:
            strategy = self._recovery_strategies[strategy_name]
            result = await strategy.apply(
                source_code,
                self.name,
                tree_sitter_parser=self._tree_sitter_parser,
                query=self._query,
                extract_fn=self.extract
            )
```

#### Recovery Metrics

```python
recovery_metrics = {
    "attempts": 0,
    "successes": 0,
    "avg_recovery_time": 0.0,
    "strategy_stats": {
        "fallback_patterns": {"attempts": 0, "successes": 0},
        "regex_fallback": {"attempts": 0, "successes": 0},
        "partial_match": {"attempts": 0, "successes": 0}
    }
}
```

#### Strategy Selection

- Dynamic strategy selection based on error type
- Strategy prioritization based on success rates
- Fallback chain configuration
- Recovery time monitoring
- Success rate tracking per strategy

### Enhanced Performance Metrics

#### Tree-Sitter Specific Metrics

```python
class TreeSitterPatternPerformanceMetrics:
    # Core metrics
    query_compilation_time: List[float] = []
    node_count: List[int] = []
    capture_count: List[int] = []
    exceeded_match_limit = 0
    exceeded_time_limit = 0
    
    # Performance tracking
    memory_usage: List[int] = []
    cache_hits = 0
    cache_misses = 0
    
    # Pattern-specific metrics
    pattern_match_counts: Dict[str, int] = defaultdict(int)
    pattern_timings: Dict[str, List[float]] = defaultdict(list)
```

#### Performance Optimization Strategies

1. **Query Analysis**:

```python
query_analysis = await ts_parser._monitor_query_performance(query_string, tree)
```

2.**Execution Strategy**:

```python
if complexity > 100:  # High complexity query
    matches = await ts_parser._execute_optimized_query(
        query_string, 
        tree,
        match_limit=1000,
        timeout_micros=50000
    )
```

3.**Caching Strategy**:

```python
cache_key = f"pattern:{self.language_id}:{pattern_name}:{hash(content)}"
cached_result = await self._pattern_cache.get(cache_key)
```

#### Memory Management

- Pattern pooling
- Result caching
- Resource cleanup
- Memory monitoring
- Garbage collection optimization

### Advanced Pattern Learning Pipeline

#### Cross-Repository Learning

```python
class TreeSitterCrossProjectPatternLearner:
    async def learn_from_repository(
        self,
        repository_path: str,
        language_id: str,
        patterns: List[Union[TreeSitterPattern, TreeSitterAdaptivePattern, TreeSitterResilientPattern]] = None,
        sample_limit: int = 100
    ) -> Dict[str, Any]:
        # Find relevant files
        language_files = await self._find_language_files(
            repository_path, language_id, sample_limit
        )
        
        # Analyze files for insights
        insights = await self._analyze_files(
            language_files, language_id, patterns
        )
        
        # Improve patterns
        for pattern in patterns:
            improved_pattern = await self._improve_pattern(
                pattern, insights[pattern_key], language_id
            )
```

#### Learning Metrics

```python
learning_metrics = {
    "total_patterns": 0,
    "learned_patterns": 0,
    "failed_patterns": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "learning_times": [],
    "pattern_improvements": {
        "node_improvements": 0,
        "capture_optimizations": 0,
        "predicate_refinements": 0,
        "pattern_generalizations": 0
    }
}
```

#### Pattern Validation with Recovery

```python
async def validate_with_recovery(
    self,
    source_code: str
) -> PatternValidationResult:
    # First try standard validation
    validation_result = await validate_tree_sitter_pattern(self)
    
    if validation_result.is_valid:
        return validation_result
        
    # Try recovery strategies
    recovery_result = await self._try_recovery_strategies(
        source_code, 
        validation_result.errors
    )
    
    # Update metrics
    if hasattr(self, 'recovery_strategies'):
        for strategy_name, strategy in self.recovery_strategies.items():
            if hasattr(strategy, 'metrics'):
                validation_result.metadata["recovery_metrics"][strategy_name] = strategy.metrics
```

### Extended Context Capabilities

#### Enhanced Pattern Context

```python
@dataclass
class TreeSitterPatternContext(BasePatternContext):
    # Tree-sitter specific context
    ast_node: Optional[Dict[str, Any]] = None
    query_captures: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    node_types: Set[str] = field(default_factory=set)
    capture_names: Set[str] = field(default_factory=set)
    syntax_errors: List[Dict[str, Any]] = field(default_factory=list)
    last_query_time: float = 0.0
    
    # Parser-specific context
    def get_parser_specific_context(self) -> Dict[str, Any]:
        return {
            "ast": self.code_structure,
            "language_id": self.language_id,
            "tree_sitter_available": True,
            "capture_points": self.metadata.get("capture_points", {}),
            "query_context": self.metadata.get("query_context", {}),
            "node_types": list(self.node_types),
            "capture_names": list(self.capture_names),
            "has_syntax_errors": bool(self.syntax_errors)
        }
```

#### Context Creation with Validation

```python
async def create_tree_sitter_context(
    file_path: str,
    code_structure: Dict[str, Any],
    learned_patterns: Optional[Dict[str, Any]] = None,
    parser_type: ParserType = ParserType.TREE_SITTER
) -> PatternContext:
    # Parse the code structure if needed
    if not code_structure:
        parse_result = await unified_parser.parse(
            file_path,
            language_id="*",
            file_type=FileType.CODE
        )
        code_structure = parse_result.ast if parse_result else {}
    
    context = PatternContext(
        code_structure=code_structure,
        language_stats={"language": "*"},
        project_patterns=list(learned_patterns.values()) if learned_patterns else [],
        file_location=file_path,
        parser_type=parser_type,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "feature_extraction_enabled": True,
            "block_extraction_enabled": True,
            "pattern_learning_enabled": True,
            "ast_available": True,
            "query_capable": True
        }
    )
```

### Health Monitoring Integration

#### Component Status Updates

```python
await global_health_monitor.update_component_status(
    "pattern_processor",
    ComponentStatus.HEALTHY,
    details={
        "patterns_loaded": len(patterns),
        "success_rate": success_rate,
        "performance_metrics": {
            "query_time_avg": metrics.get_avg_query_time(),
            "node_count_avg": metrics.get_avg_node_count(),
            "memory_usage_avg": metrics.get_avg_memory_usage()
        },
        "recovery_metrics": {
            "attempts": recovery_metrics["attempts"],
            "successes": recovery_metrics["successes"],
            "success_rate": recovery_metrics["success_rate"]
        },
        "learning_metrics": {
            "patterns_learned": learning_metrics["learned_patterns"],
            "improvement_rate": learning_metrics["improvement_rate"]
        }
    }
)
```

#### Error Tracking

```python
await ErrorAudit.record_error(
    error,
    f"pattern_processing_{self.language_id}",
    ProcessingError,
    severity=ErrorSeverity.ERROR,
    context={
        "pattern_name": pattern_name,
        "language_id": self.language_id,
        "parser_type": parser_type.value,
        "recovery_attempted": bool(recovery_result),
        "performance_metrics": metrics.to_dict()
    }
)
```

### Final Implementation Tasks

- [ ] Import required modules
- [ ] Define pattern structure
- [ ] Implement error recovery
- [ ] Add test cases
- [ ] Configure learning strategies
- [ ] Add performance monitoring
- [ ] Document usage and examples
- [ ] Review best practices
- [ ] Test thoroughly
- [ ] Monitor in production
- [ ] Implement health checks
- [ ] Configure metrics collection
- [ ] Set up error tracking
- [ ] Enable pattern learning
- [ ] Configure cross-repo analysis
- [ ] Set up recovery strategies
- [ ] Configure performance optimization
- [ ] Implement context validation
- [ ] Set up health monitoring
- [ ] Configure error auditing
- [ ] Implement memory management
- [ ] Set up pattern validation
