import os

from tree_sitter_language_pack import get_binding, get_language, get_parser


def inspect_file(file_path, language_name):
    print(f"\nInspecting {language_name} file: {file_path}")
    
    # Get parser for language
    parser = get_parser(language_name)
    
    # Read file content
    with open(file_path, 'rb') as f:
        content = f.read()
    
    # Parse file
    tree = parser.parse(content)
    
    # Function to traverse tree and collect node types
    def traverse(node, level=0):
        node_types = set()
        node_types.add(node.type)
        
        # Only print function-related nodes
        if any(t in node.type for t in ['method', 'function', 'constructor', 'closure']):
            print(f"{'  ' * level}{node.type}: {content[node.start_byte:node.end_byte].decode('utf-8').strip()}")
        
        for child in node.children:
            child_types = traverse(child, level + 1)
            node_types.update(child_types)
            
        return node_types
    
    # Traverse and collect all node types
    all_types = traverse(tree.root_node)
    print("\nAll node types found:")
    for t in sorted(all_types):
        print(f"- {t}")

# Only test Groovy file
inspect_file('tests/data/sample.groovy', 'groovy') 