"""Custom parser for HTML with enhanced documentation and structure features."""

from typing import Dict, List, Any
from parsers.common_parser_utils import build_parser_output
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape
import re
from utils.logger import log

def parse_html_code(source_code: str) -> dict:
    """
    Parse HTML content as structured code while preserving documentation features.
    
    Handles:
    - Document structure (elements, attributes, metadata)
    - Documentation (comments, meta tags, schema)
    - Script and style blocks
    - Template syntax
    - Inline documentation
    """
    features: Dict[str, Any] = {
        "syntax": {
            "elements": [],      # HTML elements
            "attributes": [],    # Element attributes
            "scripts": [],       # Script blocks
            "styles": [],        # Style blocks
            "templates": []      # Template syntax
        },
        "structure": {
            "head": None,        # Head section
            "body": None,        # Body section
            "sections": [],      # Semantic sections
            "navigation": [],    # Nav elements
            "forms": []          # Form structures
        },
        "semantics": {
            "meta": [],         # Meta information
            "links": [],        # Links and references
            "schema": [],       # Schema.org markup
            "aria": []          # Accessibility attributes
        },
        "documentation": {
            "comments": [],     # HTML comments
            "doctype": None,    # DOCTYPE declaration
            "metadata": {},     # Document metadata
            "descriptions": []  # Content descriptions
        }
    }
    
    # Enhanced patterns for HTML parsing
    patterns = {
        'comment': re.compile(r'<!--(.*?)-->', re.DOTALL),
        'doctype': re.compile(r'<!DOCTYPE\s+([^>]+)>', re.DOTALL),
        'meta': re.compile(r'<meta\s+([^>]+)>', re.DOTALL),
        'script': re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL),
        'style': re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL),
        'template': re.compile(r'{[{%].*?[%}]}', re.DOTALL)
    }
    
    def process_element(element: ET.Element, path: List[str], depth: int) -> Dict:
        """Process an HTML element and its children."""
        tag = element.tag.lower()  # HTML is case-insensitive
        
        element_data = {
            "type": "element",
            "tag": tag,
            "path": '/'.join(path + [tag]),
            "depth": depth,
            "attributes": [],
            "children": [],
            "has_text": bool(element.text and element.text.strip())
        }
        
        # Process attributes with enhanced HTML features
        for name, value in element.attrib.items():
            attr_data = {
                "name": name.lower(),
                "value": value,
                "element_path": element_data["path"]
            }
            
            # Classify special attributes
            if name.startswith('data-'):
                features["semantics"]["meta"].append(attr_data)
            elif name.startswith('aria-') or name == 'role':
                features["semantics"]["aria"].append(attr_data)
            elif name in ('itemscope', 'itemtype', 'itemprop'):
                features["semantics"]["schema"].append(attr_data)
            
            element_data["attributes"].append(attr_data)
            features["syntax"]["attributes"].append(attr_data)
        
        # Process children
        for child in element:
            child_data = process_element(child, path + [tag], depth + 1)
            element_data["children"].append(child_data)
        
        # Track special elements
        if tag == 'meta':
            features["semantics"]["meta"].append(element_data)
        elif tag == 'nav':
            features["structure"]["navigation"].append(element_data)
        elif tag == 'form':
            features["structure"]["forms"].append(element_data)
        elif tag == 'section' or tag == 'article':
            features["structure"]["sections"].append(element_data)
        
        features["syntax"]["elements"].append(element_data)
        return element_data
    
    try:
        # Process pre-parsing content
        original_content = source_code
        
        # Extract and store comments
        for match in patterns['comment'].finditer(source_code):
            comment_content = match.group(1).strip()
            features["documentation"]["comments"].append({
                "content": comment_content,
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract and store DOCTYPE
        doctype_match = patterns['doctype'].search(source_code)
        if doctype_match:
            features["documentation"]["doctype"] = {
                "content": doctype_match.group(1).strip(),
                "start": doctype_match.start(),
                "end": doctype_match.end()
            }
        
        # Extract and store scripts
        for match in patterns['script'].finditer(source_code):
            features["syntax"]["scripts"].append({
                "content": match.group(1).strip(),
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract and store styles
        for match in patterns['style'].finditer(source_code):
            features["syntax"]["styles"].append({
                "content": match.group(1).strip(),
                "start": match.start(),
                "end": match.end()
            })
        
        # Extract template syntax
        for match in patterns['template'].finditer(source_code):
            features["syntax"]["templates"].append({
                "content": match.group(0),
                "start": match.start(),
                "end": match.end()
            })
        
        # Parse HTML content
        root = ET.fromstring(source_code)
        
        # Build AST
        ast = {
            "type": "html_document",
            "root": process_element(root, [], 0),
            "start_point": [0, 0],
            "end_point": [len(source_code.splitlines()) - 1, 
                         len(source_code.splitlines()[-1]) if source_code.splitlines() else 0],
            "start_byte": 0,
            "end_byte": len(source_code)
        }
        
        # Extract documentation
        documentation = "\n".join(
            comment["content"] for comment in features["documentation"]["comments"]
        )
        
        # Calculate complexity
        complexity = (
            len(features["syntax"]["elements"]) +
            len(features["syntax"]["attributes"]) +
            len(features["syntax"]["scripts"]) +
            len(features["syntax"]["styles"])
        )
        
        return build_parser_output(
            source_code=source_code,
            language="html",
            ast=ast,
            features=features,
            total_lines=len(source_code.splitlines()),
            documentation=documentation,
            complexity=complexity
        )
        
    except Exception as e:
        log(f"Error in HTML parser: {e}", level="error")
        return build_parser_output(
            source_code=source_code,
            language="html",
            ast={"type": "error", "message": str(e)},
            features={},
            total_lines=len(source_code.splitlines()),
            documentation="",
            complexity=0
        ) 