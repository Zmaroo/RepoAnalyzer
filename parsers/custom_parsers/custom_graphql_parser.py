"""
Custom GraphQL parser.

This parser uses regexes to capture common GraphQL definitions such as type, interface,
enum, or schema definitions from a GraphQL file.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output
import re

def parse_graphql_code(source_code: str) -> dict:
    """
    Parse GraphQL schema files to generate an AST aligned with PATTERN_CATEGORIES.
    
    Maps GraphQL constructs to standard categories:
    - syntax: types (class), fields (function)
    - structure: interfaces (namespace), fragments (import)
    - documentation: descriptions (docstring), comments (comment)
    - semantics: arguments (variable), directives (expression)
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    # Regex patterns for GraphQL parsing
    type_pattern = re.compile(r'^type\s+(\w+)(?:\s+implements\s+(\w+))?\s*{')
    interface_pattern = re.compile(r'^interface\s+(\w+)\s*{')
    field_pattern = re.compile(r'^\s*(\w+)(?:\(([^)]*)\))?\s*:\s*(\w+)(!?\[?!?\]?)')
    comment_pattern = re.compile(r'^\s*#\s*(.*)$')
    description_pattern = re.compile(r'^\s*"""(.*?)"""', re.DOTALL)
    fragment_pattern = re.compile(r'^fragment\s+(\w+)\s+on\s+(\w+)')
    directive_pattern = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
    
    current_type = None
    current_interface = None
    current_description = None
    
    def process_arguments(args_str: str) -> list:
        """Process field arguments into variable nodes."""
        if not args_str:
            return []
            
        arg_nodes = []
        args = [arg.strip() for arg in args_str.split(',')]
        for arg in args:
            if ':' in arg:
                name, type_str = arg.split(':', 1)
                arg_nodes.append({
                    "type": "semantics",
                    "category": "variable",
                    "name": name.strip(),
                    "value_type": type_str.strip()
                })
        return arg_nodes

    def process_directives(line: str) -> list:
        """Extract directives as expression nodes."""
        directives = []
        for match in directive_pattern.finditer(line):
            name, args = match.groups()
            directives.append({
                "type": "semantics",
                "category": "expression",
                "name": name,
                "arguments": process_arguments(args) if args else []
            })
        return directives

    i = 0
    while i < total_lines:
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # Check for descriptions
        desc_match = description_pattern.match(line)
        if desc_match:
            current_description = {
                "type": "documentation",
                "category": "docstring",
                "content": desc_match.group(1).strip(),
                "line": i + 1
            }
            children.append(current_description)
            i += 1
            continue
            
        # Check for comments
        comment_match = comment_pattern.match(line)
        if comment_match:
            children.append({
                "type": "documentation",
                "category": "comment",
                "content": comment_match.group(1),
                "line": i + 1
            })
            i += 1
            continue
            
        # Check for types
        type_match = type_pattern.match(line)
        if type_match:
            name, implements = type_match.groups()
            type_node = {
                "type": "syntax",
                "category": "class",
                "name": name,
                "implements": implements,
                "line": i + 1,
                "children": []
            }
            if implements:
                type_node["interfaces"] = [{
                    "type": "structure",
                    "category": "import",
                    "name": implements
                }]
            current_type = type_node
            children.append(current_type)
            i += 1
            continue
            
        # Check for interfaces
        interface_match = interface_pattern.match(line)
        if interface_match:
            name = interface_match.group(1)
            interface_node = {
                "type": "structure",
                "category": "namespace",
                "name": name,
                "line": i + 1,
                "children": []
            }
            current_interface = interface_node
            children.append(current_interface)
            i += 1
            continue
            
        # Check for fields
        field_match = field_pattern.match(line)
        if field_match and (current_type or current_interface):
            name, args, return_type, modifiers = field_match.groups()
            field_node = {
                "type": "syntax",
                "category": "function",
                "name": name,
                "return_type": return_type + (modifiers or ''),
                "line": i + 1,
                "arguments": process_arguments(args) if args else [],
                "directives": process_directives(line)
            }
            
            if current_type:
                current_type["children"].append(field_node)
            else:
                current_interface["children"].append(field_node)
                
        # Check for fragments
        fragment_match = fragment_pattern.match(line)
        if fragment_match:
            name, on_type = fragment_match.groups()
            children.append({
                "type": "structure",
                "category": "import",
                "name": name,
                "target": on_type,
                "line": i + 1
            })
            
        i += 1
    
    # Build the AST root
    ast = {
        "type": "module",
        "category": "structure",
        "children": children,
        "start_point": [0, 0],
        "end_point": [total_lines - 1, len(lines[-1]) if lines else 0],
        "start_byte": 0,
        "end_byte": len(source_code)
    }

    # Extract features based on pattern categories
    features = {
        "syntax": {
            "class": [node for node in children 
                     if node["type"] == "syntax" and node["category"] == "class"],
            "function": [node for node in ast["children"] 
                        if node["type"] == "syntax" and node["category"] == "function"]
        },
        "structure": {
            "namespace": [node for node in children 
                         if node["type"] == "structure" and node["category"] == "namespace"],
            "import": [node for node in children 
                      if node["type"] == "structure" and node["category"] == "import"]
        },
        "semantics": {
            "variable": [node for node in ast["children"] 
                        if node["type"] == "semantics" and node["category"] == "variable"],
            "expression": [node for node in ast["children"] 
                         if node["type"] == "semantics" and node["category"] == "expression"]
        },
        "documentation": {
            "comment": [node for node in children 
                       if node["type"] == "documentation" and node["category"] == "comment"],
            "docstring": [node for node in children 
                         if node["type"] == "documentation" and node["category"] == "docstring"]
        }
    }

    # Extract documentation from descriptions and comments
    documentation = "\n".join(
        node["content"] for node in children
        if node["type"] == "documentation"
    )

    return build_parser_output(
        source_code=source_code,
        language="graphql",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )