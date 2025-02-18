"""Custom parser for XML with enhanced documentation and structure features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape
import re
from utils.logger import log

def parse_xml_code(source_code: str) -> dict:
    """
    Parse XML content as structured code while preserving documentation features.
    
    Handles:
    - Document structure (elements, attributes, namespaces)
    - Documentation (comments, DocType, processing instructions)
    - Schema information
    - CDATA sections
    - Mixed content (text and elements)
    """
    features: Dict[str, Any] = {
        "syntax": {
            "elements": [],      # XML elements
            "attributes": [],    # Element attributes
            "namespaces": [],   # XML namespaces
            "entities": []       # Entity declarations
        },
        "structure": {
            "hierarchy": [],     # Element hierarchy
            "references": [],    # Internal references
            "includes": []       # External references
        },
        "semantics": {
            "schemas": [],       # Schema references
            "datatypes": [],     # Data type definitions
            "identifiers": []    # IDs and IDREFs
        },
        "documentation": {
            "comments": [],      # XML comments
            "processing": [],    # Processing instructions
            "doctype": None,     # DOCTYPE declaration
            "cdata": []          # CDATA sections
        }
    }
    
    # Regex patterns for XML parsing
    patterns = {
        'comment': re.compile(r'<!--(.*?)-->', re.DOTALL),
        'processing': re.compile(r'<\?(.*?)\?>', re.DOTALL),
        'doctype': re.compile(r'<!DOCTYPE\s+([^>]+)>', re.DOTALL),
        'cdata': re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL),
        'namespace': re.compile(r'xmlns(?::(\w+))?="([^"]+)"'),
        'entity': re.compile(r'<!ENTITY\s+(\w+)\s+"([^"]+)">')
    }
    
    def process_element(element: ET.Element, path: List[str], depth: int) -> Dict:
        """Process an XML element and its children."""
        # Get the full tag name with namespace
        tag = element.tag
        namespace = None
        if '}' in tag:
            namespace, tag = tag[1:].split('}')
        
        element_data = {
            "type": "element",
            "tag": tag,
            "namespace": namespace,
            "path": '/'.join(path + [tag]),
            "depth": depth,
            "attributes": [],
            "children": [],
            "has_text": element.text and element.text.strip()
        }
        
        # Process attributes
        for name, value in element.attrib.items():
            attr_data = {
                "name": name,
                "value": value,
                "element_path": element_data["path"]
            }
            
            # Check for special attributes
            if name.startswith('xmlns'):
                features["syntax"]["namespaces"].append({
                    "prefix": name[6:] if ':' in name else None,
                    "uri": value,
                    "element_path": element_data["path"]
                })
            elif name in ('id', 'xml:id'):
                features["semantics"]["identifiers"].append({
                    "type": "id",
                    "value": value,
                    "element_path": element_data["path"]
                })
            elif name.endswith('ref'):
                features["semantics"]["identifiers"].append({
                    "type": "reference",
                    "value": value,
                    "element_path": element_data["path"]
                })
            
            element_data["attributes"].append(attr_data)
            features["syntax"]["attributes"].append(attr_data)
        
        # Process child elements
        for child in element:
            child_data = process_element(
                child,
                path + [tag],
                depth + 1
            )
            element_data["children"].append(child_data)
        
        features["syntax"]["elements"].append(element_data)
        features["structure"]["hierarchy"].append({
            "element": tag,
            "path": element_data["path"],
            "depth": depth
        })
        
        return element_data
    
    try:
        # Process pre-parsing content (comments, processing instructions, etc.)
        # Store original content for preservation
        original_content = source_code
        
        # Extract and store comments
        for match in patterns['comment'].finditer(source_code):
            features["documentation"]["comments"].append({
                "content": match.group(1).strip(),
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract and store processing instructions
        for match in patterns['processing'].finditer(source_code):
            pi_content = match.group(1).strip()
            pi_data = {
                "content": pi_content,
                "start": match.start(),
                "end": match.end()
            }
            
            # Check for schema references
            if 'schemaLocation' in pi_content:
                features["semantics"]["schemas"].append(pi_data)
            
            features["documentation"]["processing"].append(pi_data)
        
        # Extract and store DOCTYPE
        doctype_match = patterns['doctype'].search(source_code)
        if doctype_match:
            features["documentation"]["doctype"] = {
                "content": doctype_match.group(1).strip(),
                "start": doctype_match.start(),
                "end": doctype_match.end()
            }
        
        # Extract and store CDATA sections
        for match in patterns['cdata'].finditer(source_code):
            features["documentation"]["cdata"].append({
                "content": match.group(1),
                "start": match.start(),
                "end": match.end()
            })
        
        # Parse XML content
        root = ET.fromstring(source_code)
        
        # Build AST starting from root
        ast = {
            "type": "xml_document",
            "root": process_element(root, [], 0),
            "start_point": [0, 0],
            "end_point": [len(source_code.splitlines()) - 1, 
                         len(source_code.splitlines()[-1]) if source_code.splitlines() else 0],
            "start_byte": 0,
            "end_byte": len(source_code)
        }
        
        # Extract documentation from comments
        documentation = "\n".join(
            comment["content"] for comment in features["documentation"]["comments"]
        )
        
        # Calculate complexity based on structure
        complexity = (
            len(features["syntax"]["elements"]) +
            len(features["syntax"]["attributes"]) +
            len(features["structure"]["hierarchy"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="xml",
            ast=ast,
            features=features,
            total_lines=len(source_code.splitlines()),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in XML parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="xml",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 