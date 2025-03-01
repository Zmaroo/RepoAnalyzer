"""AST parsing utilities for RepoAnalyzer.

This module provides utilities for parsing and caching Abstract Syntax Trees (ASTs)
for files in repositories.
"""

import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import hashlib

from utils.logger import log
from utils.error_handling import ErrorBoundary, AsyncErrorBoundary
from utils.cache import ast_cache
from parsers.language_mapping import detect_language
from parsers.language_support import language_registry
from parsers.types import FileType, ParserType
from parsers.models import FileClassification

async def parse_files_for_cache(file_paths: List[str]) -> Dict[str, Any]:
    """
    Parse ASTs for multiple files and prepare them for caching.
    
    Args:
        file_paths: List of file paths to parse
        
    Returns:
        Dictionary mapping file paths to their ASTs
    """
    result = {}
    
    async with AsyncErrorBoundary(operation_name="batch_parse_files_for_cache"):
        # Process files in parallel with a reasonable concurrency limit
        semaphore = asyncio.Semaphore(10)  # Limit concurrent parsing
        
        async def process_file(file_path: str) -> Tuple[str, Optional[Dict[str, Any]]]:
            async with semaphore:
                try:
                    ast = await parse_file_for_cache(file_path)
                    return file_path, ast
                except Exception as e:
                    log(f"Error parsing {file_path}: {str(e)}", level="error")
                    return file_path, None
        
        # Create tasks for all files
        tasks = [process_file(path) for path in file_paths]
        
        # Wait for all tasks to complete
        for completed_task in asyncio.as_completed(tasks):
            file_path, ast = await completed_task
            if ast:
                result[file_path] = ast
    
    log(f"Parsed {len(result)} ASTs out of {len(file_paths)} files", level="info")
    return result

async def parse_file_for_cache(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parse AST for a single file and prepare it for caching.
    
    Args:
        file_path: Path to the file to parse
        
    Returns:
        AST dictionary if successful, None otherwise
    """
    if not os.path.exists(file_path):
        log(f"File not found: {file_path}", level="error")
        return None
    
    async with AsyncErrorBoundary(operation_name=f"parse_file_{file_path}"):
        # Read file content
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Generate cache key
        source_hash = hashlib.md5(content.encode('utf8')).hexdigest()
        cache_key = f"ast_file:{file_path}:{source_hash}"
        
        # Check if already in cache
        cached_ast = await ast_cache.get_async(cache_key)
        if cached_ast:
            log(f"AST cache hit for {file_path}", level="debug")
            return cached_ast
        
        # Detect language
        language_id, confidence = detect_language(file_path, content)
        if confidence < 0.6:
            log(f"Low confidence ({confidence:.2f}) language detection for {file_path}", level="warning")
        
        # Get parser
        classification = FileClassification(
            file_type=FileType.CODE,  # Assume code file by default
            language_id=language_id,
            parser_type=ParserType.TREE_SITTER  # Prefer tree-sitter parsers
        )
        
        parser = language_registry.get_parser(classification)
        if not parser:
            # Try with a more general parser
            classification.parser_type = ParserType.CUSTOM
            parser = language_registry.get_parser(classification)
            
        if not parser:
            log(f"No parser found for {file_path} with language {language_id}", level="error")
            return None
        
        # Parse the file
        parse_result = parser.parse(content)
        if not parse_result or not parse_result.success:
            log(f"Parsing failed for {file_path}", level="error")
            return None
        
        # Store in cache
        await ast_cache.set_async(cache_key, parse_result.ast)
        log(f"AST cached for {file_path}", level="debug")
        
        return parse_result.ast

async def get_ast_for_file(file_path: str, content: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get AST for a file, using cache if available.
    
    Args:
        file_path: Path to the file
        content: Optional content (if already loaded)
        
    Returns:
        AST dictionary if available, None otherwise
    """
    # If content not provided, read from file
    if content is None:
        if not os.path.exists(file_path):
            log(f"File not found: {file_path}", level="error")
            return None
            
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    
    # Generate cache key
    source_hash = hashlib.md5(content.encode('utf8')).hexdigest()
    cache_key = f"ast_file:{file_path}:{source_hash}"
    
    # Check cache
    cached_ast = await ast_cache.get_async(cache_key)
    if cached_ast:
        return cached_ast
    
    # Parse if not in cache
    return await parse_file_for_cache(file_path) 