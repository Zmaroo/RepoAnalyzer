import yaml
from parsers.common_parser_utils import extract_features_from_ast, build_parser_output

def get_yaml_type(value):
    """Determine a YAML data type from a Python value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    else:
        return "unknown"

def convert_to_ast(data):
    """
    Recursively converts Python data (obtained via PyYAML) into an AST-like
    structure including metadata for database ingestion.
    """
    if isinstance(data, dict):
        children = []
        for key, value in data.items():
            pair_node = {
                "type": "block_mapping_pair",
                "yaml_type": "mapping_pair",
                "start_point": [0, 0],
                "end_point": [0, 0],
                "start_byte": 0,
                "end_byte": 0,
                "children": [
                    {
                        # Key node for the mapping pair
                        "type": "plain_scalar",
                        "yaml_type": get_yaml_type(key),
                        "value": str(key),
                        "start_point": [0, 0],
                        "end_point": [0, 0],
                        "start_byte": 0,
                        "end_byte": 0,
                    },
                    {
                        # The colon (:) node separator
                        "type": ":",
                        "start_point": [0, 0],
                        "end_point": [0, 0],
                        "start_byte": 0,
                        "end_byte": 0,
                    },
                    # Recursively convert the value.
                    convert_to_ast(value)
                ]
            }
            children.append(pair_node)
        return {
            "type": "block_mapping",
            "yaml_type": "mapping",
            "children": children,
            "start_point": [0, 0],
            "end_point": [0, 0],
            "start_byte": 0,
            "end_byte": 0
        }
    elif isinstance(data, list):
        items = []
        for item in data:
            sequence_item = {
                "type": "block_sequence_item",
                "yaml_type": "sequence_item",
                "start_point": [0, 0],
                "end_point": [0, 0],
                "start_byte": 0,
                "end_byte": 0,
                "children": [convert_to_ast(item)]
            }
            items.append(sequence_item)
        return {
            "type": "block_sequence",
            "yaml_type": "sequence",
            "children": items,
            "start_point": [0, 0],
            "end_point": [0, 0],
            "start_byte": 0,
            "end_byte": 0
        }
    else:
        # For scalars, also capture the specific data type in 'yaml_type'.
        return {
            "type": "flow_node",
            "yaml_type": "scalar",
            "start_point": [0, 0],
            "end_point": [0, 0],
            "start_byte": 0,
            "end_byte": 0,
            "children": [
                {
                    "type": "plain_scalar",
                    "yaml_type": get_yaml_type(data),
                    "value": data,
                    "start_point": [0, 0],
                    "end_point": [0, 0],
                    "start_byte": 0,
                    "end_byte": 0,
                }
            ]
        }

def parse_yaml_code(source_code: str) -> dict:
    """
    Parse the provided YAML source code using PyYAML and extend the
    generated structure with metadata including AST positions (set to default
    values) and the YAML type for each node.
    
    The root AST node type is now set to "yaml_stream" (to match our YAML query patterns).
    """
    # Split the source into lines to compute simple positions.
    lines = source_code.splitlines()
    total_lines = len(lines)
    last_line_length = len(lines[-1]) if lines else 0

    # Change the root type from "stream" to "yaml_stream" to match our query patterns.
    stream_node = {
        "type": "yaml_stream",
        "start_point": [0, 0],
        "end_point": [total_lines - 1, last_line_length],
        "start_byte": 0,
        "end_byte": len(source_code),
        "children": []
    }
    
    # If the first line is a comment, extract it as documentation.
    documentation = ""
    current_byte = 0
    children = []
    if lines and lines[0].strip().startswith("#"):
        comment_line = lines[0]
        comment_node = {
            "type": "comment",
            "start_point": [0, 0],
            "end_point": [0, len(comment_line)],
            "start_byte": 0,
            "end_byte": len(comment_line)
        }
        children.append(comment_node)
        documentation = comment_line.strip()
        current_byte += len(comment_line) + 1  # Account for newline
        doc_start_line = 1
    else:
        doc_start_line = 0

    # Create a document node spanning the remainder of the file.
    document_node = {
        "type": "document",
        "start_point": [doc_start_line, 0],
        "end_point": [total_lines - 1, last_line_length],
        "start_byte": current_byte,
        "end_byte": len(source_code),
        "children": []
    }
    
    # Parse the YAML content using PyYAML.
    try:
        parsed_data = yaml.safe_load(source_code)
    except Exception:
        parsed_data = None
    
    if parsed_data is not None:
        block_node = {
            "type": "block_node",
            "yaml_type": "document_body",
            "start_point": [doc_start_line, 0],
            "end_point": [total_lines - 1, last_line_length],
            "start_byte": current_byte,
            "end_byte": len(source_code),
            "children": [convert_to_ast(parsed_data)]
        }
    else:
        block_node = {
            "type": "block_node",
            "yaml_type": "document_body",
            "start_point": [doc_start_line, 0],
            "end_point": [total_lines - 1, last_line_length],
            "start_byte": current_byte,
            "end_byte": len(source_code),
            "children": []
        }
    document_node["children"].append(block_node)
    children.append(document_node)
    stream_node["children"] = children
    
    features = extract_features_from_ast(stream_node)
    
    return build_parser_output(
        source_code=source_code,
        language="yaml",
        ast=stream_node,
        features=features,
        total_lines=total_lines,
        documentation=documentation,
        complexity=1
    )