"""Custom parser for Markdown with enhanced documentation features."""

from typing import Dict, List, Any, Optional
from parsers.base_parser import BaseParser
from parsers.types import FileType, PatternCategory
from parsers.models import MarkdownNode
from parsers.query_patterns.markdown import MARKDOWN_PATTERNS
from utils.logger import log
import re

class MarkdownParser(BaseParser):
    """Parser for Markdown files."""
    
    def __init__(self, language_id: str = "markdown", file_type: Optional[FileType] = None):
        super().__init__(language_id, file_type or FileType.DOCUMENTATION)
        self.patterns = {
            'header': re.compile(r'^(#{1,6})\s+(.+)$'),
            'list_item': re.compile(r'^(\s*)[*+-]\s+(.+)$'),
            'numbered_list': re.compile(r'^(\s*)\d+\.\s+(.+)$'),
            'code_block': re.compile(r'^```(\w*)$'),
            'link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)'),
            'image': re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        }

    def initialize(self) -> bool:
        """Initialize parser resources."""
        self._initialized = True
        return True

    def _create_node(
        self,
        node_type: str,
        start_point: List[int],
        end_point: List[int],
        **kwargs
    ) -> MarkdownNode:
        """Create a standardized Markdown AST node."""
        return MarkdownNode(
            type=node_type,
            start_point=start_point,
            end_point=end_point,
            children=[],
            **kwargs
        )

    def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse Markdown content into AST structure."""
        try:
            lines = source_code.splitlines()
            ast = self._create_node(
                "document",
                [0, 0],
                [len(lines) - 1, len(lines[-1]) if lines else 0]
            )
            
            current_section = None
            in_code_block = False
            code_block_content = []
            code_block_lang = None

            for i, line in enumerate(lines):
                line_start = [i, 0]
                line_end = [i, len(line)]

                # Process headers
                if not in_code_block and (header_match := self.patterns['header'].match(line)):
                    level, content = header_match.groups()
                    node = self._create_node(
                        "header",
                        line_start,
                        line_end,
                        level=len(level),
                        content=content
                    )
                    ast.children.append(node)
                    current_section = node
                    continue

                # Process code blocks
                if code_match := self.patterns['code_block'].match(line):
                    if not in_code_block:
                        in_code_block = True
                        code_block_lang = code_match.group(1)
                        code_block_content = []
                        code_block_start = line_start
                    else:
                        node = self._create_node(
                            "code_block",
                            code_block_start,
                            line_end,
                            language=code_block_lang,
                            content="\n".join(code_block_content)
                        )
                        if current_section:
                            current_section.children.append(node)
                        else:
                            ast.children.append(node)
                        in_code_block = False
                    continue

                if in_code_block:
                    code_block_content.append(line)
                    continue

                # Process lists
                if list_match := self.patterns['list_item'].match(line):
                    indent, content = list_match.groups()
                    node = self._create_node(
                        "list_item",
                        line_start,
                        line_end,
                        content=content,
                        indent=len(indent)
                    )
                    if current_section:
                        current_section.children.append(node)
                    else:
                        ast.children.append(node)

            return ast.__dict__
            
        except Exception as e:
            log(f"Error parsing Markdown content: {e}", level="error")
            return MarkdownNode(
                type="document",
                start_point=[0, 0],
                end_point=[0, 0],
                error=str(e),
                children=[]
            ).__dict__ 