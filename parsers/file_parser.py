"""High-level file processing module."""

from typing import Optional, Dict, List
from parsers.language_parser import CodeParser
from indexer.doc_index import upsert_doc
from indexer.file_utils import is_binary_file, read_text_file
from utils.logger import log
from parsers.ast_extractor import extract_doc_features
from parsers.language_mapping import (
    get_file_classification, 
    FileType,
    DocExtractionConfig, 
    CodeBlockConfig
)

class FileProcessor:
    def __init__(self):
        self.code_parser = CodeParser()
        
    def process_file(self, file_path: str, repo_id: int) -> Optional[Dict]:
        """Process a file based on its classification."""
        classification = get_file_classification(file_path)
        if not classification:
            return None
            
        source_code = read_text_file(file_path)
        if not source_code:
            return None
            
        # Use appropriate custom parser
        parsed_content = self.code_parser.parse_code(
            source_code, 
            classification.parser
        )
        
        # Extract and validate code blocks if configured
        if classification.code_block_config:
            code_blocks = self._process_code_blocks(
                parsed_content['ast_data'],
                classification.code_block_config
            )
            parsed_content['code_blocks'] = code_blocks
            
            # Update documentation content with validated code blocks
            if classification.index_as_doc:
                doc_id = upsert_doc(
                    repo_id=repo_id,
                    file_path=file_path,
                    content=source_code,
                    doc_type=classification.parser,
                    metadata={
                        'code_blocks': code_blocks,
                        'has_validated_code': True
                    }
                )
                parsed_content['doc_id'] = doc_id
                
        return parsed_content

    def _process_code_blocks(self, ast_data: dict, config: CodeBlockConfig) -> List[Dict]:
        """Process code blocks with validation and feature extraction."""
        code_blocks = []
        
        for block in ast_data.get('features', {}).get('syntax', {}).get('code_blocks', []):
            if not block.get('language') or block['language'] not in config.supported_languages:
                continue
                
            processed_block = {
                'language': block['language'],
                'content': block['content'],
                'location': {
                    'start_line': block['start_line'],
                    'end_line': block['end_line']
                }
            }
            
            if config.validate_syntax:
                try:
                    # Validate syntax using appropriate parser
                    validation = self.code_parser.parse_code(
                        block['content'],
                        block['language']
                    )
                    processed_block['is_valid'] = bool(validation.get('ast_data'))
                    processed_block['validation_error'] = validation.get('error')
                except Exception as e:
                    processed_block['is_valid'] = False
                    processed_block['validation_error'] = str(e)
            
            if config.extract_imports and processed_block.get('is_valid'):
                processed_block['imports'] = self._extract_imports(
                    validation['ast_data'],
                    block['language']
                )
                
            code_blocks.append(processed_block)
            
        return code_blocks

    def _extract_documentation(self, source_code: str, ast_data: dict, doc_config: DocExtractionConfig) -> str:
        """Extract documentation based on configuration."""
        doc_parts = []
        
        if doc_config.extract_docstrings:
            docstrings = self._extract_docstrings(ast_data)
            doc_parts.extend(docstrings)
            
        if doc_config.extract_comments:
            comments = self._extract_comments(ast_data)
            doc_parts.extend(comments)
            
        if doc_config.extract_type_hints:
            type_hints = self._extract_type_hints(ast_data)
            doc_parts.extend(type_hints)
            
        if doc_config.doc_sections:
            sections = self._extract_sections(source_code, doc_config.doc_sections)
            doc_parts.extend(sections)
            
        return '\n\n'.join(doc_parts)

    def _process_doc_file(self, content: str, ext: str, repo_id: int, file_path: str) -> Dict:
        """Handle documentation files with dual processing."""
        # Process as documentation for indexing
        doc_id = upsert_doc(repo_id, file_path, content)
        
        # Process as structured content
        parsed_content = self.code_parser.parse_code(content, f"markup_{ext[1:]}")  # e.g., "markup_md"
        features = extract_doc_features(parsed_content['ast_data'], content.encode('utf-8'))
        
        return {
            "type": "documentation",
            "content": content,
            "format": ext,
            "doc_id": doc_id,
            "ast_data": parsed_content['ast_data'],
            "ast_features": features,
            "structure": parsed_content.get('ast_features', {})
        }

    def _process_code_file(self, content: str, file_path: str) -> Dict:
        """Process as code file with proper language detection."""
        return self.code_parser.parse_code(content, file_path)