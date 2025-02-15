def parse_cobalt(file_path):
    """
    Custom parser for Cobalt source files.
    
    Reads the file content and returns a dictionary that includes the language,
    original content, and a simulated AST structure.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # For demonstration, we simulate an AST structure.
    ast_data = {
        "custom_nodes": ["cobalt_root", "function_decl"],
        "description": "Simulated AST for cobalt"
    }
    
    return {
        "language": "cobalt",
        "content": content,
        "ast_data": ast_data
    } 