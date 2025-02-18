"""
Custom Nim parser.

This parser applies simple regex patterns to extract key elements from Nim source files,
for example, procedure (proc) and type definitions.
"""

from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

import re

def parse_nim_code(source_code: str) -> dict:
    """
    Parse Nim source files to generate an AST aligned with PATTERN_CATEGORIES.
    
    Maps Nim constructs to standard categories:
    - syntax: procedures (function), types/objects (class)
    - structure: modules (namespace), imports (import)
    - documentation: doc comments (docstring), comments (comment)
    - semantics: variables/constants (variable), expressions (expression)
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    # Regex patterns for Nim parsing
    proc_pattern = re.compile(r'^proc\s+(\w+)\*?\s*\((.*?)\)(?:\s*:\s*(\w+))?\s*=')
    type_pattern = re.compile(r'^type\s+(\w+)\*?\s*=\s*(?:object|enum|tuple|ref\s+object)')
    import_pattern = re.compile(r'^import\s+(.*?)(?:\s+except\s+.*)?$')
    var_pattern = re.compile(r'^(var|let|const)\s+(\w+)\*?\s*(?::\s*(\w+))?\s*=\s*(.+)$')
    doc_comment_pattern = re.compile(r'^##\s*(.*)$')
    comment_pattern = re.compile(r'^#\s*(.*)$')
    
    def process_parameters(params_str: str) -> list:
        """Process procedure parameters into variable nodes."""
        if not params_str.strip():
            return []
            
        param_nodes = []
        params = [p.strip() for p in params_str.split(',')]
        for param in params:
            if ':' in param:
                names, type_str = param.split(':', 1)
                for name in names.split(','):
                    param_nodes.append({
                        "type": "semantics",
                        "category": "variable",
                        "name": name.strip(),
                        "value_type": type_str.strip()
                    })
        return param_nodes

    current_doc = []
    
    def flush_doc() -> dict:
        """Convert accumulated doc comments into a docstring node."""
        nonlocal current_doc
        if current_doc:
            doc_node = {
                "type": "documentation",
                "category": "docstring",
                "content": "\n".join(current_doc)
            }
            current_doc = []
            return doc_node
        return None

    i = 0
    while i < total_lines:
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            if current_doc:
                doc_node = flush_doc()
                if doc_node:
                    children.append(doc_node)
            i += 1
            continue
            
        # Check for doc comments
        doc_match = doc_comment_pattern.match(line)
        if doc_match:
            current_doc.append(doc_match.group(1))
            i += 1
            continue
            
        # Check for regular comments
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
            
        # Process any accumulated doc comments
        if current_doc:
            doc_node = flush_doc()
            if doc_node:
                children.append(doc_node)
            
        # Check for procedures
        proc_match = proc_pattern.match(line)
        if proc_match:
            name, params, return_type = proc_match.groups()
            proc_node = {
                "type": "syntax",
                "category": "function",
                "name": name,
                "parameters": process_parameters(params),
                "return_type": return_type,
                "line": i + 1
            }
            children.append(proc_node)
            i += 1
            continue
            
        # Check for types
        type_match = type_pattern.match(line)
        if type_match:
            name = type_match.group(1)
            type_node = {
                "type": "syntax",
                "category": "class",
                "name": name,
                "line": i + 1
            }
            children.append(type_node)
            i += 1
            continue
            
        # Check for imports
        import_match = import_pattern.match(line)
        if import_match:
            imports = import_match.group(1).split(',')
            for imp in imports:
                imp = imp.strip()
                if imp:
                    children.append({
                        "type": "structure",
                        "category": "import",
                        "name": imp,
                        "line": i + 1
                    })
            i += 1
            continue
            
        # Check for variables/constants
        var_match = var_pattern.match(line)
        if var_match:
            kind, name, type_str, value = var_match.groups()
            var_node = {
                "type": "semantics",
                "category": "variable",
                "name": name,
                "value_type": type_str,
                "value": value,
                "is_const": kind == "const",
                "line": i + 1
            }
            children.append(var_node)
            
        i += 1
    
    # Flush any remaining doc comments
    if current_doc:
        doc_node = flush_doc()
        if doc_node:
            children.append(doc_node)
    
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
            "function": [node for node in children 
                        if node["type"] == "syntax" and node["category"] == "function"],
            "class": [node for node in children 
                     if node["type"] == "syntax" and node["category"] == "class"]
        },
        "structure": {
            "import": [node for node in children 
                      if node["type"] == "structure" and node["category"] == "import"]
        },
        "semantics": {
            "variable": [node for node in children 
                        if node["type"] == "semantics" and node["category"] == "variable"]
        },
        "documentation": {
            "docstring": [node for node in children 
                         if node["type"] == "documentation" and node["category"] == "docstring"],
            "comment": [node for node in children 
                       if node["type"] == "documentation" and node["category"] == "comment"]
        }
    }

    # Extract documentation from doc comments and regular comments
    documentation = "\n".join(
        node["content"] for node in children
        if node["type"] == "documentation"
    )

    return build_parser_output(
        source_code=source_code,
        language="nim",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )