import os
import ast

def extract_docstrings_from_file(filepath):
    """
    Extracts the module, classes, and functions docstrings from a Python file.
    
    Args:
        filepath (str): Path to the Python file.
    
    Returns:
        dict: A dictionary containing the module docstring, list of classes, and functions with their docstrings.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        file_content = f.read()
    
    tree = ast.parse(file_content)
    doc_data = {}
    # Module-level docstring
    module_doc = ast.get_docstring(tree)
    doc_data["module_doc"] = module_doc if module_doc else ""
    
    classes = []
    functions = []
    
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "doc": ast.get_docstring(node) or "",
                "methods": []
            }
            for subnode in node.body:
                if isinstance(subnode, ast.FunctionDef):
                    method_doc = ast.get_docstring(subnode) or ""
                    class_info["methods"].append({
                        "name": subnode.name,
                        "doc": method_doc
                    })
            classes.append(class_info)
        elif isinstance(node, ast.FunctionDef):
            # Top-level module function.
            functions.append({
                "name": node.name,
                "doc": ast.get_docstring(node) or ""
            })
    
    doc_data["classes"] = classes
    doc_data["functions"] = functions
    return doc_data

def generate_markdown(doc_data, filename):
    """
    Generates Markdown content for the provided doc_data.
    
    Args:
        doc_data (dict): Documentation data extracted from a Python module.
        filename (str): The original file name.
    
    Returns:
        str: Markdown formatted documentation.
    """
    md = f"# Documentation for {filename}\n\n"
    
    if doc_data.get("module_doc"):
        md += "## Module Description\n\n"
        md += f"{doc_data['module_doc']}\n\n"
    
    if doc_data.get("classes"):
        md += "## Classes\n\n"
        for cls in doc_data["classes"]:
            md += f"### Class: {cls['name']}\n\n"
            if cls.get("doc"):
                md += f"{cls['doc']}\n\n"
            if cls.get("methods"):
                md += "#### Methods:\n\n"
                for method in cls["methods"]:
                    md += f"- **{method['name']}**: {method['doc']}\n"
                md += "\n"
    
    if doc_data.get("functions"):
        md += "## Functions\n\n"
        for func in doc_data["functions"]:
            md += f"- **{func['name']}**: {func['doc']}\n"
    
    return md

def update_documentation(ai_tools_dir="ai_tools", ai_tools_docs_dir="ai_tools_docs"):
    """
    Scans the ai_tools directory for .py files, generates corresponding Markdown documentation,
    and saves it to the ai_tools_docs directory, preserving directory structure.
    
    Args:
        ai_tools_dir (str): Source directory containing implementation.
        ai_tools_docs_dir (str): Destination directory for documentation.
    """
    if not os.path.exists(ai_tools_docs_dir):
        os.makedirs(ai_tools_docs_dir)
    
    for root, dirs, files in os.walk(ai_tools_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                print(f"Processing {file_path} ...")
                doc_data = extract_docstrings_from_file(file_path)
                md_content = generate_markdown(doc_data, file)
                
                # Maintain directory structure relative to ai_tools
                relative_path = os.path.relpath(file_path, ai_tools_dir)
                md_file_name = os.path.splitext(relative_path)[0] + ".md"
                output_path = os.path.join(ai_tools_docs_dir, md_file_name)
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                print(f"Documentation updated at: {output_path}")

if __name__ == "__main__":
    update_documentation() 