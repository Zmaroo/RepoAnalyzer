"""React-specific analyzer for JSX components and React patterns.

This module provides a dedicated React analyzer for processing React components,
hooks, and JSX elements in JavaScript and TypeScript files.
"""
import json
from typing import Dict, Any, List, Optional, Union, Set, Tuple
from dataclasses import dataclass, field
import os
import asyncio
import time
from collections import defaultdict
from parsers.types import (
    PatternCategory, PatternPurpose, PatternType, PatternRelationType,
    PatternContext, PatternRelationship, PatternPerformanceMetrics,
    PatternValidationResult, PatternMatchResult, QueryPattern,
    AICapability, AIContext, AIProcessingResult, InteractionType,
    ExtractedFeatures, FileType, ParserType
)
from parsers.models import PATTERN_CATEGORIES
from utils.health_monitor import global_health_monitor, ComponentStatus
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity
from .common import (
    COMMON_PATTERNS,
    process_tree_sitter_pattern,
    validate_tree_sitter_pattern,
    create_tree_sitter_context
)
from .enhanced_patterns import (
    TreeSitterPattern,
    TreeSitterAdaptivePattern,
    TreeSitterResilientPattern,
    TreeSitterCrossProjectPatternLearner,
    DATA_DIR
)
from .tree_sitter_utils import execute_tree_sitter_query, count_nodes, extract_captures
from .js_ts_shared import (
    JS_TS_SHARED_PATTERNS,
    process_js_ts_pattern,
    JSTSPatternLearner,
    JS_TS_CAPABILITIES,
    create_js_ts_pattern_context
)
from parsers.pattern_processor import pattern_processor

# Module identification
LANGUAGE = "react"

# React-specific capabilities
REACT_CAPABILITIES = JS_TS_CAPABILITIES | {
    AICapability.JSX_SUPPORT,
    AICapability.REACT_INTEGRATION
}

# React-specific patterns
REACT_PATTERNS = {
    PatternCategory.COMPONENTS: {
        PatternPurpose.UNDERSTANDING: {
            "functional_component": TreeSitterPattern(
                name="functional_component",
                pattern="""
                [
                    (function_declaration
                        name: (identifier) @component.func.name
                        parameters: (formal_parameters
                            (identifier)* @component.func.param) @component.func.params
                        body: (statement_block) @component.func.body) @component.func,
                        
                    (arrow_function
                        parameters: (formal_parameters
                            (identifier)* @component.arrow.param) @component.arrow.params
                        body: [(statement_block) @component.arrow.body, (_) @component.arrow.expr]) @component.arrow
                ]
                """,
                category=PatternCategory.COMPONENTS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="react",
                confidence=0.9,
                extract=lambda m: {
                    "type": "react_component",
                    "component_type": "functional",
                    "name": m["captures"]["component.func.name"]["text"] if "component.func.name" in m.get("captures", {}) else "AnonymousComponent",
                    "params": [p["text"] for p in m["captures"].get("component.func.param", []) + m["captures"].get("component.arrow.param", [])],
                    "has_jsx_return": any("<" in body["text"] for body in m["captures"].get("component.func.body", []) + m["captures"].get("component.arrow.body", []) + m["captures"].get("component.arrow.expr", []))
                },
                regex_pattern=r'(function\s+([A-Z][a-zA-Z0-9]*)\s*\([^)]*\)\s*{|const\s+([A-Z][a-zA-Z0-9]*)\s*=\s*\([^)]*\)\s*=>)',
                block_type="react_component",
                contains_blocks=["jsx_element"],
                is_nestable=True,
                metadata={
                    "description": "Matches React functional components",
                    "examples": [
                        "function Button(props) { return <button>{props.label}</button>; }",
                        "const Profile = ({ name }) => <div>{name}</div>;"
                    ],
                    "version": "1.0",
                    "tags": ["react", "component", "functional", "jsx"]
                },
                test_cases=[
                    {
                        "input": "function Button(props) { return <button>{props.label}</button>; }",
                        "expected": {
                            "type": "react_component",
                            "component_type": "functional",
                            "name": "Button",
                            "has_jsx_return": True
                        }
                    },
                    {
                        "input": "const Profile = ({ name }) => <div>{name}</div>;",
                        "expected": {
                            "type": "react_component",
                            "component_type": "functional",
                            "has_jsx_return": True
                        }
                    }
                ]
            ),
            
            "react_hook": TreeSitterPattern(
                name="react_hook",
                pattern="""
                [
                    (lexical_declaration
                        (variable_declarator
                            name: (_) @hook.declaration.name
                            value: (call_expression
                                function: (identifier) @hook.declaration.function
                                arguments: (arguments) @hook.declaration.arguments))) @hook.declaration
                ]
                """,
                category=PatternCategory.COMPONENTS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="react",
                confidence=0.9,
                extract=lambda m: {
                    "type": "react_hook",
                    "hook_type": m["captures"]["hook.declaration.function"]["text"] if "hook.declaration.function" in m.get("captures", {}) else "",
                    "is_useState": "useState" in m["captures"]["hook.declaration.function"]["text"] if "hook.declaration.function" in m.get("captures", {}) else False,
                    "is_useEffect": "useEffect" in m["captures"]["hook.declaration.function"]["text"] if "hook.declaration.function" in m.get("captures", {}) else False,
                    "is_custom_hook": m["captures"]["hook.declaration.function"]["text"].startswith("use") if "hook.declaration.function" in m.get("captures", {}) else False
                },
                regex_pattern=r'const\s+(?:\[[^\]]+\]|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*use[A-Z][a-zA-Z]*\(',
                block_type="react_hook",
                is_nestable=False,
                metadata={
                    "description": "Matches React hook calls",
                    "examples": [
                        "const [count, setCount] = useState(0);",
                        "useEffect(() => { document.title = 'Hello'; }, []);"
                    ],
                    "version": "1.0",
                    "tags": ["react", "hook", "useState", "useEffect"]
                },
                test_cases=[
                    {
                        "input": "const [count, setCount] = useState(0);",
                        "expected": {
                            "type": "react_hook",
                            "hook_type": "useState",
                            "is_useState": True
                        }
                    },
                    {
                        "input": "useEffect(() => { document.title = 'Hello'; }, []);",
                        "expected": {
                            "type": "react_hook",
                            "hook_type": "useEffect",
                            "is_useEffect": True
                        }
                    }
                ]
            ),
            
            "component_props": TreeSitterPattern(
                name="component_props",
                pattern="""
                [
                    (pair
                        key: (property_identifier) @props.pair.key
                        value: (_) @props.pair.value) @props.pair,
                        
                    (jsx_attribute
                        name: (property_identifier) @props.jsx.name
                        value: (_)? @props.jsx.value) @props.jsx
                ]
                """,
                category=PatternCategory.COMPONENTS,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="react",
                confidence=0.9,
                extract=lambda m: {
                    "type": "react_props",
                    "prop_name": m["captures"]["props.pair.key"]["text"] if "props.pair.key" in m.get("captures", {}) else m["captures"]["props.jsx.name"]["text"] if "props.jsx.name" in m.get("captures", {}) else "",
                    "is_jsx": "props.jsx.name" in m.get("captures", {}),
                    "has_value": "props.jsx.value" in m.get("captures", {}) or "props.pair.value" in m.get("captures", {}),
                    "is_event_handler": m["captures"]["props.jsx.name"]["text"].startswith("on") if "props.jsx.name" in m.get("captures", {}) else False
                },
                regex_pattern=r'([a-z][a-zA-Z]*?)(?:=(?:"[^"]*"|\'[^\']*\'|\{[^}]*\}))?',
                block_type="props",
                is_nestable=False,
                metadata={
                    "description": "Matches React component props",
                    "examples": [
                        "className=\"container\"",
                        "onClick={handleClick}"
                    ],
                    "version": "1.0",
                    "tags": ["react", "props", "attribute"]
                },
                test_cases=[
                    {
                        "input": "className=\"container\"",
                        "expected": {
                            "type": "react_props",
                            "prop_name": "className",
                            "has_value": True,
                            "is_event_handler": False
                        }
                    },
                    {
                        "input": "onClick={handleClick}",
                        "expected": {
                            "type": "react_props", 
                            "prop_name": "onClick",
                            "has_value": True,
                            "is_event_handler": True
                        }
                    }
                ]
            )
        }
    },
    
    PatternCategory.COMMON_ISSUES: {
        PatternPurpose.UNDERSTANDING: {
            "dependency_array_issue": TreeSitterPattern(
                name="dependency_array_issue",
                pattern="""
                [
                    (call_expression
                        function: (identifier) @issue.deps.function
                        arguments: (arguments
                            (arrow_function) @issue.deps.callback
                            (array) @issue.deps.array)) @issue.deps
                ]
                """,
                category=PatternCategory.COMMON_ISSUES,
                purpose=PatternPurpose.UNDERSTANDING,
                language_id="react",
                confidence=0.8,
                extract=lambda m: {
                    "type": "dependency_array_issue",
                    "hook_type": m["captures"]["issue.deps.function"]["text"] if "issue.deps.function" in m.get("captures", {}) else "",
                    "dependencies": m["captures"]["issue.deps.array"]["text"] if "issue.deps.array" in m.get("captures", {}) else "[]",
                    "callback": m["captures"]["issue.deps.callback"]["text"] if "issue.deps.callback" in m.get("captures", {}) else "",
                    "potential_issue": "issue.deps.array" in m.get("captures", {}) and m["captures"]["issue.deps.array"]["text"] == "[]" and "setState" in m["captures"]["issue.deps.callback"]["text"] if "issue.deps.callback" in m.get("captures", {}) else False
                },
                regex_pattern=r'use(?:Effect|Callback|Memo)\(\s*\(\)\s*=>\s*{\s*.*?\s*}\s*,\s*\[\s*\]\s*\)',
                block_type="react_issue",
                is_nestable=False,
                metadata={
                    "description": "Detects potential issues with React hook dependency arrays",
                    "examples": [
                        "useEffect(() => { setCount(count + 1); }, [])",
                        "useCallback(() => { setValue(data.value); }, [])"
                    ],
                    "version": "1.0",
                    "tags": ["react", "hook", "dependency", "issue"]
                },
                test_cases=[
                    {
                        "input": "useEffect(() => { setCount(count + 1); }, [])",
                        "expected": {
                            "type": "dependency_array_issue",
                            "hook_type": "useEffect",
                            "potential_issue": True
                        }
                    }
                ]
            )
        }
    }
}

@dataclass
class ReactComponent:
    """Represents a React component with its properties and relationships."""
    name: str
    type: str  # 'functional', 'class', 'memo', 'forwardRef', etc.
    file_path: str
    line_start: int
    line_end: int
    props: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hooks: List[Dict[str, Any]] = field(default_factory=list)
    state_vars: List[Dict[str, Any]] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    parent_components: List[str] = field(default_factory=list)
    is_exported: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert component to dictionary representation."""
        return {
            "name": self.name,
            "type": self.type,
            "file_path": self.file_path,
            "line_range": {
                "start": self.line_start,
                "end": self.line_end
            },
            "props": self.props,
            "hooks": self.hooks,
            "state_vars": self.state_vars,
            "children": self.children,
            "parent_components": self.parent_components,
            "is_exported": self.is_exported
        }

@dataclass
class ReactHook:
    """Represents a React hook with its properties and relationships."""
    name: str
    hook_type: str  # 'useState', 'useEffect', 'useContext', etc.
    file_path: str
    line_number: int
    dependencies: List[str] = field(default_factory=list)
    component_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert hook to dictionary representation."""
        return {
            "name": self.name,
            "hook_type": self.hook_type,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "dependencies": self.dependencies,
            "component_name": self.component_name
        }

class ReactAnalyzer:
    """Specialized analyzer for React components and patterns."""
    
    def __init__(self):
        """Initialize the React analyzer."""
        self.components: Dict[str, ReactComponent] = {}
        self.hooks: Dict[str, ReactHook] = {}
        self.jsx_elements: List[Dict[str, Any]] = []
        self.component_hierarchy: Dict[str, List[str]] = {}
        self.insights_path = os.path.join(DATA_DIR, "react_insights.json")
        
        # Learning and metrics tracking
        self.learning_metrics = {
            "patterns_learned": 0,
            "components_analyzed": 0,
            "hooks_analyzed": 0,
            "avg_analysis_time": 0.0,
            "analysis_times": []
        }
        
        # Recovery metrics
        self.recovery_metrics = {
            "attempts": 0,
            "successes": 0,
            "success_rate": 0.0,
            "strategy_stats": {
                "fallback_jsx": {"attempts": 0, "successes": 0},
                "partial_jsx": {"attempts": 0, "successes": 0},
                "hook_analysis": {"attempts": 0, "successes": 0}
            }
        }
        
        # Pattern learning
        self.learned_patterns = []
        self.pattern_variations = defaultdict(list)
    
    @classmethod
    async def create(cls) -> 'ReactAnalyzer':
        """Create and initialize a ReactAnalyzer instance."""
        analyzer = cls()
        await analyzer.initialize()
        return analyzer
    
    async def initialize(self):
        """Initialize the analyzer with required components."""
        # Load previous insights if available
        await self._load_insights()
        
        # Register patterns with pattern processor
        from parsers.pattern_processor import pattern_processor
        if pattern_processor:
            await pattern_processor.register_language_patterns(
                "react",
                REACT_PATTERNS,
                metadata={
                    "parser_type": ParserType.TREE_SITTER,
                    "supports_learning": True,
                    "supports_adaptation": True,
                    "capabilities": REACT_CAPABILITIES
                }
            )
        
        # Register health monitoring
        await global_health_monitor.update_component_status(
            "react_analyzer",
            ComponentStatus.HEALTHY,
            details={
                "components_tracked": len(self.components),
                "hooks_tracked": len(self.hooks),
                "capabilities": list(REACT_CAPABILITIES),
                "patterns_learned": len(self.learned_patterns)
            }
        )
    
    async def _load_insights(self) -> None:
        """Load previously saved insights."""
        try:
            if os.path.exists(self.insights_path):
                with open(self.insights_path, 'r') as f:
                    data = json.load(f)
                    
                    # Load data
                    self.components = {
                        name: ReactComponent(**comp_data) 
                        for name, comp_data in data.get("components", {}).items()
                    }
                    self.hooks = {
                        name: ReactHook(**hook_data)
                        for name, hook_data in data.get("hooks", {}).items()
                    }
                    self.jsx_elements = data.get("jsx_elements", [])
                    self.component_hierarchy = data.get("component_hierarchy", {})
                    self.learned_patterns = data.get("learned_patterns", [])
                    
                await log(
                    f"Loaded React analyzer insights", 
                    level="info",
                    context={
                        "components": len(self.components),
                        "hooks": len(self.hooks),
                        "learned_patterns": len(self.learned_patterns)
                    }
                )
        except Exception as e:
            await log(
                f"Could not load React analyzer insights: {e}",
                level="warning"
            )
    
    async def analyze_component(
        self,
        component_match: Dict[str, Any],
        file_path: str,
        context: Optional[PatternContext] = None
    ) -> ReactComponent:
        """Analyze a React component from a pattern match."""
        start_time = time.time()
        
        component = ReactComponent(
            name=component_match.get("name", "UnnamedComponent"),
            type=component_match.get("component_type", "functional"),
            file_path=file_path,
            line_start=component_match.get("line_start", 0),
            line_end=component_match.get("line_end", 0),
            is_exported=component_match.get("is_exported", False)
        )
        
        # Process props
        if "props" in component_match:
            for prop_name, prop_info in component_match["props"].items():
                component.props[prop_name] = {
                    "type": prop_info.get("type", "any"),
                    "required": prop_info.get("required", False),
                    "has_default": prop_info.get("has_default", False)
                }
        
        # Process hooks
        if "hooks" in component_match:
            for hook_info in component_match["hooks"]:
                hook = ReactHook(
                    name=hook_info.get("name", ""),
                    hook_type=hook_info.get("hook_type", ""),
                    file_path=file_path,
                    line_number=hook_info.get("line_number", 0),
                    dependencies=hook_info.get("dependencies", []),
                    component_name=component.name
                )
                component.hooks.append(hook.to_dict())
                
                # Add to hooks dictionary
                if hook.name:
                    self.hooks[hook.name] = hook
                
                # Add state variables if it's a useState hook
                if hook.hook_type == "useState":
                    if "state_var" in hook_info:
                        component.state_vars.append({
                            "name": hook_info["state_var"],
                            "setter": hook_info.get("setter", f"set{hook_info['state_var'][0].upper()}{hook_info['state_var'][1:]}"),
                            "initial_value": hook_info.get("initial_value", None)
                        })
        
        # Add to components dictionary
        self.components[component.name] = component
        
        # Update learning metrics
        self.learning_metrics["components_analyzed"] += 1
        analysis_time = time.time() - start_time
        self.learning_metrics["analysis_times"].append(analysis_time)
        
        # Update average analysis time
        total_analyses = self.learning_metrics["components_analyzed"] + self.learning_metrics["hooks_analyzed"]
        if total_analyses > 0:
            self.learning_metrics["avg_analysis_time"] = (
                sum(self.learning_metrics["analysis_times"]) / len(self.learning_metrics["analysis_times"])
            )
        
        # Learn patterns from component
        if context and context.get("enable_learning", True):
            await self.learn_from_component(component, file_path, context)
        
        return component
    
    async def analyze_jsx_element(
        self, 
        jsx_match: Dict[str, Any],
        file_path: str,
        context: Optional[PatternContext] = None
    ) -> Dict[str, Any]:
        """Analyze a JSX element from a pattern match."""
        element_name = jsx_match.get("element_name", "")
        is_component = jsx_match.get("is_component", False)
        
        # For components (capitalized names), track parent-child relationships
        if is_component and element_name:
            # Get current component context if available
            current_component = context.get("current_component") if context else None
            
            if current_component:
                # Add this element as a child of the current component
                if current_component in self.components:
                    if element_name not in self.components[current_component].children:
                        self.components[current_component].children.append(element_name)
                
                # Add current component as parent of this element
                if element_name in self.components:
                    if current_component not in self.components[element_name].parent_components:
                        self.components[element_name].parent_components.append(current_component)
                
                # Update component hierarchy
                if current_component not in self.component_hierarchy:
                    self.component_hierarchy[current_component] = []
                if element_name not in self.component_hierarchy[current_component]:
                    self.component_hierarchy[current_component].append(element_name)
        
        # Add to JSX elements list
        element_info = {
            "name": element_name,
            "is_component": is_component,
            "file_path": file_path,
            "has_children": jsx_match.get("has_children", False),
            "is_self_closing": jsx_match.get("is_self_closing", False),
            "attributes": jsx_match.get("attributes", {})
        }
        self.jsx_elements.append(element_info)
        
        # Try to recover additional information if needed
        if context and context.get("enable_recovery", True) and not element_info["attributes"]:
            try:
                self.recovery_metrics["attempts"] += 1
                self.recovery_metrics["strategy_stats"]["fallback_jsx"]["attempts"] += 1
                
                # Try to extract attributes from match data
                attributes = {}
                if "captures" in jsx_match:
                    for capture_name, capture_data in jsx_match["captures"].items():
                        if "jsx_attr" in capture_name and capture_data:
                            attr_name = None
                            attr_value = None
                            
                            if "name" in capture_name and capture_data[0]["text"]:
                                attr_name = capture_data[0]["text"]
                            
                            if "value" in capture_name and capture_data[0]["text"]:
                                attr_value = capture_data[0]["text"]
                            
                            if attr_name:
                                attributes[attr_name] = attr_value
                
                if attributes:
                    element_info["attributes"] = attributes
                    self.recovery_metrics["successes"] += 1
                    self.recovery_metrics["strategy_stats"]["fallback_jsx"]["successes"] += 1
            except Exception as e:
                await log(f"Error in JSX attribute recovery: {e}", level="warning")
        
        # Update recovery success rate
        if self.recovery_metrics["attempts"] > 0:
            self.recovery_metrics["success_rate"] = (
                self.recovery_metrics["successes"] / self.recovery_metrics["attempts"]
            )
        
        return element_info
    
    async def analyze_hook(
        self,
        hook_match: Dict[str, Any],
        file_path: str,
        context: Optional[PatternContext] = None
    ) -> ReactHook:
        """Analyze a React hook from a pattern match."""
        start_time = time.time()
        
        hook_name = hook_match.get("hook_name", "")
        hook_type = hook_match.get("hook_type", "")
        if not hook_type and "hook_call" in hook_match:
            # Extract hook type from the hook call
            hook_call = hook_match["hook_call"]
            if "use" in hook_call:
                parts = hook_call.split("use")
                if len(parts) > 1:
                    hook_type = "use" + parts[1].split("(")[0]
        
        # Get current component context if available
        component_name = context.get("current_component") if context else None
        
        hook = ReactHook(
            name=hook_name,
            hook_type=hook_type,
            file_path=file_path,
            line_number=hook_match.get("line_number", 0),
            dependencies=hook_match.get("dependencies", []),
            component_name=component_name
        )
        
        # Try to recover dependencies if not provided
        if context and context.get("enable_recovery", True) and not hook.dependencies and hook.hook_type in ["useEffect", "useCallback", "useMemo"]:
            try:
                self.recovery_metrics["attempts"] += 1
                self.recovery_metrics["strategy_stats"]["hook_analysis"]["attempts"] += 1
                
                # Simple regex-based dependency extraction
                if "hook_call" in hook_match:
                    hook_call = hook_match["hook_call"]
                    # Look for dependency array like: }, [dep1, dep2])
                    import re
                    deps_match = re.search(r'\}, \[(.*?)\]\)', hook_call)
                    if deps_match:
                        deps_str = deps_match.group(1)
                        # Split and clean up dependencies
                        dependencies = [d.strip() for d in deps_str.split(',') if d.strip()]
                        if dependencies:
                            hook.dependencies = dependencies
                            self.recovery_metrics["successes"] += 1
                            self.recovery_metrics["strategy_stats"]["hook_analysis"]["successes"] += 1
            except Exception as e:
                await log(f"Error in hook dependency recovery: {e}", level="warning")
        
        # Add to hooks dictionary
        if hook.name:
            self.hooks[hook.name] = hook
            
            # If hook belongs to a component, add it to the component's hooks
            if component_name and component_name in self.components:
                self.components[component_name].hooks.append(hook.to_dict())
        
        # Update learning metrics
        self.learning_metrics["hooks_analyzed"] += 1
        analysis_time = time.time() - start_time
        self.learning_metrics["analysis_times"].append(analysis_time)
        
        # Update average analysis time
        total_analyses = self.learning_metrics["components_analyzed"] + self.learning_metrics["hooks_analyzed"]
        if total_analyses > 0:
            self.learning_metrics["avg_analysis_time"] = (
                sum(self.learning_metrics["analysis_times"]) / len(self.learning_metrics["analysis_times"])
            )
        
        # Update recovery success rate
        if self.recovery_metrics["attempts"] > 0:
            self.recovery_metrics["success_rate"] = (
                self.recovery_metrics["successes"] / self.recovery_metrics["attempts"]
            )
        
        return hook
    
    async def learn_from_component(
        self, 
        component: ReactComponent,
        file_path: str,
        context: Optional[PatternContext]
    ) -> None:
        """Learn patterns from a React component."""
        try:
            # Extract component patterns
            component_pattern = {
                "type": "react_component",
                "name": component.name,
                "component_type": component.type,
                "file_path": file_path,
                "props": list(component.props.keys()),
                "has_state": bool(component.state_vars),
                "hooks_used": [hook.get("hook_type") for hook in component.hooks],
                "confidence": 0.85,
                "learned": True,
                "timestamp": time.time(),
                "category": PatternCategory.COMPONENTS.value if hasattr(PatternCategory.COMPONENTS, "value") else "COMPONENTS"
            }
            
            # Learn hooks pattern if component has hooks
            if component.hooks:
                hooks_pattern = {
                    "type": "react_hooks",
                    "component_name": component.name,
                    "hooks": [h.get("hook_type") for h in component.hooks],
                    "file_path": file_path,
                    "has_state_hooks": any(h.get("hook_type") == "useState" for h in component.hooks),
                    "has_effect_hooks": any(h.get("hook_type") == "useEffect" for h in component.hooks),
                    "confidence": 0.8,
                    "learned": True,
                    "timestamp": time.time(),
                    "category": PatternCategory.CODE_PATTERNS.value if hasattr(PatternCategory.CODE_PATTERNS, "value") else "CODE_PATTERNS"
                }
                
                self.learned_patterns.append(hooks_pattern)
                self.learning_metrics["patterns_learned"] += 1
            
            # Add component pattern to learned patterns
            self.learned_patterns.append(component_pattern)
            self.learning_metrics["patterns_learned"] += 1
            
            # Learn component structure pattern based on hierarchy
            if component.name in self.component_hierarchy:
                structure_pattern = {
                    "type": "react_component_structure",
                    "root_component": component.name,
                    "children": self.component_hierarchy[component.name],
                    "file_path": file_path,
                    "confidence": 0.75,
                    "learned": True,
                    "timestamp": time.time(),
                    "category": PatternCategory.ARCHITECTURE.value if hasattr(PatternCategory.ARCHITECTURE, "value") else "ARCHITECTURE"
                }
                
                self.learned_patterns.append(structure_pattern)
                self.learning_metrics["patterns_learned"] += 1
            
        except Exception as e:
            await log(f"Error learning from component: {e}", level="warning")
    
    async def learn_from_repository(
        self,
        repo_path: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Learn React patterns from a repository.
        
        Args:
            repo_path: Path to the repository
            limit: Maximum number of files to analyze
            
        Returns:
            Dict with learning results
        """
        results = {
            "components_found": 0,
            "hooks_found": 0,
            "patterns_learned": 0,
            "files_analyzed": 0
        }
        
        try:
            # Find React files (JSX/TSX)
            jsx_files = []
            tsx_files = []
            
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith(".jsx"):
                        jsx_files.append(os.path.join(root, file))
                    elif file.endswith(".tsx"):
                        tsx_files.append(os.path.join(root, file))
                        
                    if len(jsx_files) + len(tsx_files) >= limit:
                        break
                        
                if len(jsx_files) + len(tsx_files) >= limit:
                    break
            
            # Analyze files
            react_files = jsx_files + tsx_files
            for file_path in react_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Create context
                    context = {"enable_learning": True, "enable_recovery": True}
                    
                    # Use appropriate parser based on file extension
                    if file_path.endswith(".jsx"):
                        await self._analyze_jsx_file(content, file_path, context)
                    elif file_path.endswith(".tsx"):
                        await self._analyze_tsx_file(content, file_path, context)
                    
                    results["files_analyzed"] += 1
                    
                except Exception as e:
                    await log(f"Error analyzing file {file_path}: {e}", level="warning")
            
            # Update results
            results["components_found"] = len(self.components)
            results["hooks_found"] = len(self.hooks)
            results["patterns_learned"] = len(self.learned_patterns)
            
            # Save insights
            await self.save_insights()
            
            return results
            
        except Exception as e:
            await log(f"Error learning from repository: {e}", level="error")
            return results
    
    async def _analyze_jsx_file(self, content: str, file_path: str, context: Dict[str, Any]):
        """Analyze a JSX file for React patterns."""
        from parsers.query_patterns.javascript import get_javascript_pattern_relationships
        
        # Get JavaScript parser
        from parsers.pattern_processor import pattern_processor
        js_processor = await pattern_processor.get_language_processor("javascript")
        
        if js_processor:
            # Process with JavaScript patterns
            result = await js_processor.parse(content, file_path)
            
            # Extract React components and hooks from result
            if result.features:
                components = result.features.get("components", [])
                for component in components:
                    await self.analyze_component(component, file_path, context)
                
                hooks = result.features.get("hooks", [])
                for hook in hooks:
                    await self.analyze_hook(hook, file_path, context)
                
                jsx_elements = result.features.get("jsx_elements", [])
                for element in jsx_elements:
                    await self.analyze_jsx_element(element, file_path, context)
    
    async def _analyze_tsx_file(self, content: str, file_path: str, context: Dict[str, Any]):
        """Analyze a TSX file for React patterns."""
        from parsers.query_patterns.typescript import get_typescript_pattern_relationships
        
        # Get TypeScript parser
        from parsers.pattern_processor import pattern_processor
        ts_processor = await pattern_processor.get_language_processor("typescript")
        
        if ts_processor:
            # Process with TypeScript patterns
            result = await ts_processor.parse(content, file_path)
            
            # Extract React components and hooks from result
            if result.features:
                components = result.features.get("components", [])
                for component in components:
                    await self.analyze_component(component, file_path, context)
                
                hooks = result.features.get("hooks", [])
                for hook in hooks:
                    await self.analyze_hook(hook, file_path, context)
                
                jsx_elements = result.features.get("jsx_elements", [])
                for element in jsx_elements:
                    await self.analyze_jsx_element(element, file_path, context)
    
    async def get_component_hierarchy(self) -> Dict[str, Any]:
        """Get the component hierarchy as a nested structure."""
        hierarchy = {}
        
        for component_name, children in self.component_hierarchy.items():
            hierarchy[component_name] = await self._build_hierarchy_recursive(component_name, set())
        
        return hierarchy
    
    async def _build_hierarchy_recursive(self, component_name: str, visited: Set[str]) -> Dict[str, Any]:
        """Recursively build component hierarchy."""
        if component_name in visited:
            # Avoid circular references
            return {"name": component_name, "children": ["[Circular Reference]"]}
        
        visited.add(component_name)
        
        children = self.component_hierarchy.get(component_name, [])
        child_nodes = []
        
        for child in children:
            if child in self.component_hierarchy:
                child_nodes.append(await self._build_hierarchy_recursive(child, visited.copy()))
            else:
                child_nodes.append({"name": child, "children": []})
        
        return {
            "name": component_name,
            "children": child_nodes
        }
    
    async def get_hook_usage(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get aggregated hook usage statistics."""
        hook_usage = {}
        
        for hook in self.hooks.values():
            hook_type = hook.hook_type
            if hook_type not in hook_usage:
                hook_usage[hook_type] = []
            
            hook_usage[hook_type].append(hook.to_dict())
        
        return hook_usage
    
    async def get_prop_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get aggregated prop usage across components."""
        prop_usage = {}
        
        for component in self.components.values():
            for prop_name, prop_info in component.props.items():
                if prop_name not in prop_usage:
                    prop_usage[prop_name] = {
                        "components": [],
                        "types": set(),
                        "required_count": 0,
                        "optional_count": 0
                    }
                
                # Add component using this prop
                prop_usage[prop_name]["components"].append(component.name)
                
                # Add prop type
                prop_usage[prop_name]["types"].add(prop_info.get("type", "any"))
                
                # Update required/optional counts
                if prop_info.get("required", False):
                    prop_usage[prop_name]["required_count"] += 1
                else:
                    prop_usage[prop_name]["optional_count"] += 1
        
        # Convert sets to lists for JSON serialization
        for prop_data in prop_usage.values():
            prop_data["types"] = list(prop_data["types"])
        
        return prop_usage
    
    async def analyze_component_patterns(self) -> Dict[str, Any]:
        """Analyze common patterns across React components."""
        patterns = {
            "render_optimization": {
                "memo_usage": 0,
                "callback_usage": 0
            },
            "state_management": {
                "local_state": 0,
                "context_usage": 0,
                "redux_usage": 0
            },
            "component_types": {
                "functional": 0,
                "class": 0,
                "hoc": 0
            }
        }
        
        for component in self.components.values():
            # Component types
            if component.type == "functional":
                patterns["component_types"]["functional"] += 1
            elif component.type == "class":
                patterns["component_types"]["class"] += 1
            elif component.type in ["memo", "forwardRef"]:
                patterns["component_types"]["hoc"] += 1
            
            # Optimization techniques
            if component.type == "memo":
                patterns["render_optimization"]["memo_usage"] += 1
            
            # Check hooks for optimization and state management patterns
            for hook in component.hooks:
                hook_type = hook.get("hook_type", "")
                if hook_type == "useCallback" or hook_type == "useMemo":
                    patterns["render_optimization"]["callback_usage"] += 1
                elif hook_type == "useState":
                    patterns["state_management"]["local_state"] += 1
                elif hook_type == "useContext":
                    patterns["state_management"]["context_usage"] += 1
                elif hook_type in ["useSelector", "useDispatch", "useStore"]:
                    patterns["state_management"]["redux_usage"] += 1
        
        return patterns
    
    async def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        return self.recovery_metrics
    
    async def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        return self.learning_metrics
    
    async def save_insights(self):
        """Save React analyzer insights to file."""
        insights = {
            "components": {name: comp.to_dict() for name, comp in self.components.items()},
            "hooks": {name: hook.to_dict() for name, hook in self.hooks.items()},
            "component_hierarchy": await self.get_component_hierarchy(),
            "hook_usage": await self.get_hook_usage(),
            "prop_usage": await self.get_prop_usage(),
            "patterns": await self.analyze_component_patterns(),
            "learned_patterns": self.learned_patterns,
            "learning_metrics": self.learning_metrics,
            "recovery_metrics": self.recovery_metrics,
            "timestamp": time.time()
        }
        
        import json
        os.makedirs(os.path.dirname(self.insights_path), exist_ok=True)
        with open(self.insights_path, 'w') as f:
            json.dump(insights, f, indent=2)
        
        return insights

# Initialize global analyzer instance (will be properly initialized in setup)
react_analyzer = ReactAnalyzer()

async def initialize_react_analyzer():
    """Initialize React analyzer during app startup."""
    global react_analyzer
    react_analyzer = await ReactAnalyzer.create()
    
    await global_health_monitor.update_component_status(
        "react_analyzer", 
        ComponentStatus.HEALTHY,
        details={
            "status": "initialized",
            "capabilities": list(REACT_CAPABILITIES)
        }
    )
    
    return react_analyzer

class ReactPatternLearner(TreeSitterCrossProjectPatternLearner):
    """React pattern learner with cross-project learning capabilities."""
    
    def __init__(self):
        """Initialize React pattern learner."""
        super().__init__("react_pattern_learner")
        self.insights_path = os.path.join(DATA_DIR, "react_pattern_insights.json")
        self.learning_strategies = {}
        self.recovery_strategies = {}
    
    @classmethod
    async def create(cls) -> 'ReactPatternLearner':
        """Create and initialize a ReactPatternLearner instance."""
        learner = cls()
        await learner.initialize()
        return learner
    
    async def initialize(self):
        """Initialize React pattern learner."""
        await super().initialize()
        
        # Load learning strategies
        from .learning_strategies import get_learning_strategies
        self.learning_strategies = get_learning_strategies()
        
        # Load recovery strategies
        from .recovery_strategies import get_recovery_strategies
        self.recovery_strategies = get_recovery_strategies()
        
        # Register React patterns
        from parsers.pattern_processor import register_pattern
        for category, purpose_dict in REACT_PATTERNS.items():
            for purpose, patterns in purpose_dict.items():
                for name, pattern in patterns.items():
                    pattern_key = f"{category}:{purpose}:{name}"
                    await register_pattern(pattern_key, pattern)
        
        # Update health monitoring
        await global_health_monitor.update_component_status(
            "react_pattern_learner",
            ComponentStatus.HEALTHY,
            details={
                "patterns_loaded": sum(len(patterns) for purpose_dict in REACT_PATTERNS.values() for patterns in purpose_dict.values()),
                "learning_strategies": list(self.learning_strategies.keys()),
                "recovery_strategies": list(self.recovery_strategies.keys()),
                "capabilities": list(REACT_CAPABILITIES)
            }
        )
    
    async def learn_from_file(self, file_path: str, language_id: str = "react") -> Dict[str, Any]:
        """Learn patterns from a single file."""
        results = {
            "patterns_learned": 0,
            "file_analyzed": file_path,
            "patterns": []
        }
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Determine file type (jsx or tsx)
            is_tsx = file_path.endswith(".tsx")
            actual_language = "typescript" if is_tsx else "javascript"
            
            # Get tree-sitter parser
            from parsers.tree_sitter_parser import get_tree_sitter_parser
            ts_parser = await get_tree_sitter_parser(actual_language)
            
            if not ts_parser:
                return results
            
            # Parse file
            tree = ts_parser.parse(content)
            
            # Apply patterns to extract components and hooks
            for category, purpose_dict in REACT_PATTERNS.items():
                for purpose, patterns in purpose_dict.items():
                    for name, pattern in patterns.items():
                        # Only apply patterns relevant to the file type
                        if (is_tsx and pattern.language_id in ["react", "tsx"]) or \
                           (not is_tsx and pattern.language_id in ["react", "javascript"]):
                            try:
                                # Execute query
                                matches = await ts_parser.execute_pattern(pattern, tree, content)
                                
                                if matches:
                                    # Extract learned patterns
                                    for match in matches:
                                        learned_pattern = {
                                            "type": match.get("type", name),
                                            "category": category.value if hasattr(category, "value") else str(category),
                                            "purpose": purpose.value if hasattr(purpose, "value") else str(purpose),
                                            "confidence": pattern.confidence,
                                            "file_path": file_path,
                                            "learned": True,
                                            "timestamp": time.time(),
                                            "language_id": actual_language,
                                            "pattern_name": name,
                                            "match_data": match
                                        }
                                        
                                        results["patterns"].append(learned_pattern)
                                        results["patterns_learned"] += 1
                            except Exception as e:
                                await log(f"Error applying pattern {name}: {e}", level="warning")
            
            return results
            
        except Exception as e:
            await log(f"Error learning from file {file_path}: {e}", level="error")
            return results
    
    async def apply_learning_strategies(self, pattern: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply learning strategies to improve a pattern."""
        pattern_str = pattern.get("pattern", "")
        if not pattern_str:
            return None
        
        insights = pattern.get("match_data", {})
        language_id = pattern.get("language_id", "react")
        
        # Apply each strategy in sequence
        for strategy_name, strategy in self.learning_strategies.items():
            try:
                improved = await strategy.apply(pattern_str, insights, language_id)
                if improved:
                    pattern["pattern"] = improved["pattern"]
                    pattern["confidence"] = improved["confidence"]
                    pattern["strategy_applied"] = strategy_name
                    return pattern
            except Exception as e:
                await log(f"Error applying strategy {strategy_name}: {e}", level="warning")
        
        return None
    
    async def learn_from_project(self, repo_path: str, limit: int = 100) -> Dict[str, Any]:
        """Learn React patterns from a project.
        
        Args:
            repo_path: Path to the repository
            limit: Maximum number of files to analyze
            
        Returns:
            Dict with learning results
        """
        results = {
            "files_analyzed": 0,
            "patterns_learned": 0,
            "components_found": 0,
            "hooks_found": 0,
            "patterns": []
        }
        
        try:
            # Find React files (JSX/TSX)
            react_files = []
            
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if file.endswith(".jsx") or file.endswith(".tsx"):
                        react_files.append(os.path.join(root, file))
                        
                        if len(react_files) >= limit:
                            break
                
                if len(react_files) >= limit:
                    break
            
            # Analyze files
            for file_path in react_files:
                try:
                    file_results = await self.learn_from_file(file_path)
                    
                    # Update results
                    results["files_analyzed"] += 1
                    results["patterns_learned"] += file_results["patterns_learned"]
                    results["patterns"].extend(file_results["patterns"])
                    
                    # Count components and hooks
                    for pattern in file_results["patterns"]:
                        if pattern.get("type") == "react_component":
                            results["components_found"] += 1
                        elif pattern.get("type") == "react_hook":
                            results["hooks_found"] += 1
                    
                except Exception as e:
                    await log(f"Error analyzing file {file_path}: {e}", level="warning")
            
            # Apply learning strategies to patterns
            improved_patterns = []
            for pattern in results["patterns"]:
                improved = await self.apply_learning_strategies(pattern)
                if improved:
                    improved_patterns.append(improved)
            
            # Save insights
            await self._save_insights(results)
            
            return results
            
        except Exception as e:
            await log(f"Error learning from project: {e}", level="error")
            return results
    
    async def _save_insights(self, results: Dict[str, Any]) -> None:
        """Save insights to file."""
        import json
        os.makedirs(os.path.dirname(self.insights_path), exist_ok=True)
        
        try:
            # Load existing insights if available
            existing_insights = {}
            if os.path.exists(self.insights_path):
                with open(self.insights_path, 'r') as f:
                    existing_insights = json.load(f)
            
            # Update with new insights
            insights = {
                "patterns": existing_insights.get("patterns", []) + results.get("patterns", []),
                "metrics": {
                    "total_files_analyzed": existing_insights.get("metrics", {}).get("total_files_analyzed", 0) + results.get("files_analyzed", 0),
                    "total_patterns_learned": existing_insights.get("metrics", {}).get("total_patterns_learned", 0) + results.get("patterns_learned", 0),
                    "components_found": existing_insights.get("metrics", {}).get("components_found", 0) + results.get("components_found", 0),
                    "hooks_found": existing_insights.get("metrics", {}).get("hooks_found", 0) + results.get("hooks_found", 0)
                },
                "timestamp": time.time()
            }
            
            # Save to file
            with open(self.insights_path, 'w') as f:
                json.dump(insights, f, indent=2)
            
        except Exception as e:
            await log(f"Error saving React pattern insights: {e}", level="warning")

# Initialize pattern learner (will be initialized during startup)
react_pattern_learner = ReactPatternLearner()

async def initialize_react_patterns():
    """Initialize React patterns during app startup."""
    global react_pattern_learner
    
    # Initialize pattern processor
    await pattern_processor.initialize()
    
    # Register React patterns
    await pattern_processor.register_language_patterns(
        "react",
        REACT_PATTERNS,
        metadata={
            "parser_type": ParserType.TREE_SITTER,
            "supports_learning": True,
            "supports_adaptation": True,
            "capabilities": REACT_CAPABILITIES
        }
    )
    
    # Initialize React analyzer
    global react_analyzer
    react_analyzer = await ReactAnalyzer.create()
    
    # Initialize pattern learner
    react_pattern_learner = await ReactPatternLearner.create()
    
    # Register learner with pattern processor
    await pattern_processor.register_pattern_learner(
        "react",
        react_pattern_learner
    )
    
    # Update health status
    await global_health_monitor.update_component_status(
        "react_patterns",
        ComponentStatus.HEALTHY,
        details={
            "patterns_loaded": sum(len(patterns) for purpose_dict in REACT_PATTERNS.values() for patterns in purpose_dict.values()),
            "capabilities": list(REACT_CAPABILITIES),
            "analyzer_ready": True,
            "learner_ready": True
        }
    )

# Update public exports
__all__ = [
    'ReactAnalyzer',
    'react_analyzer',
    'ReactPatternLearner',
    'react_pattern_learner',
    'initialize_react_analyzer',
    'initialize_react_patterns',
    'REACT_CAPABILITIES',
    'REACT_PATTERNS'
] 