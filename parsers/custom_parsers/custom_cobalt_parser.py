"""
Custom parser for the Cobalt programming language.
"""

from parsers.common_parser_utils import build_parser_output, extract_features_from_ast
import re

def parse_cobalt(source_code: str) -> dict:
    """
    Parse Cobalt source files to generate an AST aligned with PATTERN_CATEGORIES.
    
    Maps Cobalt constructs to standard categories:
    - syntax: functions (function), classes/types (class)
    - structure: modules (namespace), imports (import)
    - documentation: doc strings (docstring), comments (comment)
    - semantics: variables (variable), expressions (expression)
    """
    lines = source_code.splitlines()
    total_lines = len(lines)
    children = []
    
    # Regex patterns for Cobalt parsing
    func_pattern = re.compile(r'^fn\s+(\w+)\s*\((.*?)\)(?:\s*->\s*(\w+))?\s*{')
    class_pattern = re.compile(r'^class\s+(\w+)(?:\s*:\s*(\w+))?\s*{')
    import_pattern = re.compile(r'^import\s+([\w.]+)(?:\s+as\s+(\w+))?$')
    var_pattern = re.compile(r'^(let|var)\s+(\w+)(?:\s*:\s*(\w+))?(?:\s*=\s*(.+))?$')
    doc_pattern = re.compile(r'^///\s*(.*)$')
    comment_pattern = re.compile(r'^//\s*(.*)$')
    
    current_doc = []
    
    def flush_doc():
        if current_doc:
            content = '\n'.join(current_doc)
            current_doc.clear()
            return {
                "type": "documentation",
                "category": "docstring",
                "content": content
            }
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
            
        # Check for doc strings
        doc_match = doc_pattern.match(line)
        if doc_match:
            current_doc.append(doc_match.group(1))
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
            
        # Process any accumulated doc strings
        if current_doc:
            doc_node = flush_doc()
            if doc_node:
                children.append(doc_node)
        
        # Check for functions
        func_match = func_pattern.match(line)
        if func_match:
            name, params, return_type = func_match.groups()
            func_node = {
                "type": "syntax",
                "category": "function",
                "name": name,
                "parameters": [p.strip() for p in params.split(',') if p.strip()],
                "return_type": return_type,
                "line": i + 1
            }
            children.append(func_node)
            i += 1
            continue
            
        # Check for classes
        class_match = class_pattern.match(line)
        if class_match:
            name, parent = class_match.groups()
            class_node = {
                "type": "syntax",
                "category": "class",
                "name": name,
                "parent": parent,
                "line": i + 1
            }
            children.append(class_node)
            i += 1
            continue
            
        # Check for imports
        import_match = import_pattern.match(line)
        if import_match:
            path, alias = import_match.groups()
            import_node = {
                "type": "structure",
                "category": "import",
                "path": path,
                "alias": alias,
                "line": i + 1
            }
            children.append(import_node)
            i += 1
            continue
            
        # Check for variables
        var_match = var_pattern.match(line)
        if var_match:
            kind, name, type_str, value = var_match.groups()
            var_node = {
                "type": "semantics",
                "category": "variable",
                "name": name,
                "value_type": type_str,
                "value": value,
                "is_mutable": kind == "var",
                "line": i + 1
            }
            children.append(var_node)
            
        i += 1
    
    # Flush any remaining doc strings
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
            "namespace": [node for node in children 
                         if node["type"] == "structure" and node["category"] == "namespace"],
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
    
    # Extract documentation from doc strings and comments
    documentation = "\n".join(
        node["content"] for node in children
        if node["type"] == "documentation"
    )
    
    return build_parser_output(
        source_code=source_code,
        language="cobalt",
        ast=ast,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    ) 