#!/usr/bin/env python3
"""
Comprehensive Pipeline Test for RepoAnalyzer

This script tests each component of the RepoAnalyzer pipeline in isolation:
1. Language detection
2. Parser selection and AST generation
3. Feature extraction
4. Database operations
5. Graph projection
6. Semantic search

This allows testing individual components and identifying issues in specific parts of the pipeline.
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
import time
import json
import traceback
from typing import Dict, List, Any, Optional

# Try to import RepoAnalyzer components
try:
    # Core components
    from db.psql import query, close_db_pool
    from db.neo4j_ops import get_neo4j_driver, get_connection_config, auto_reinvoke_projection_once
    from db.schema import create_all_tables, drop_all_tables
    from indexer.file_utils import get_files, is_processable_file, get_relative_path
    from parsers.language_mapping import detect_language_from_filename, detect_language_from_content
    from parsers.language_support import language_registry
    from parsers.types import ParserResult, FileType
    from semantic.search import search_code, search_docs
    from utils.logger import log
    from utils.error_handling import ErrorBoundary
    from embedding.embedding_models import code_embedder, doc_embedder
    from ai_tools.graph_capabilities import graph_analysis
    HAS_IMPORTS = True
except ImportError as e:
    print(f"Could not import RepoAnalyzer modules: {e}")
    HAS_IMPORTS = False

class PipelineTest:
    """Handles testing of individual pipeline components."""
    
    def __init__(self, repo_path=None, clean_db=False):
        self.repo_path = repo_path or os.getcwd()
        self.clean_db = clean_db
        self.sample_files = {}
        self.repo_id = None
        self.results = {}
    
    async def setup(self):
        """Set up the test environment."""
        if self.clean_db:
            print("Cleaning databases...")
            await drop_all_tables()
            await create_all_tables()
        
        # Create repository record
        repo_name = os.path.basename(os.path.abspath(self.repo_path))
        repo_records = await query(
            "INSERT INTO repositories (repo_name, repo_type) VALUES (%s, %s) ON CONFLICT (repo_name) DO UPDATE SET repo_name = %s RETURNING id",
            (repo_name, 'active', repo_name)
        )
        self.repo_id = repo_records[0]['id']
        print(f"Using repository ID: {self.repo_id}")
        
        # Find sample files
        print("Finding sample files for testing...")
        self._find_sample_files()
        
        print("Setup complete.")
    
    def _find_sample_files(self):
        """Find representative sample files of different types for testing."""
        extensions = {'.py', '.js', '.html', '.md', '.json', '.txt', '.yml'}
        max_files_per_ext = 2
        
        all_files = get_files(self.repo_path)
        
        for file_path in all_files:
            if not is_processable_file(file_path):
                continue
                
            _, ext = os.path.splitext(file_path)
            if ext in extensions:
                if ext not in self.sample_files:
                    self.sample_files[ext] = []
                
                if len(self.sample_files[ext]) < max_files_per_ext:
                    self.sample_files[ext].append(file_path)
        
        # Print summary of sample files
        print("Sample files for testing:")
        for ext, files in self.sample_files.items():
            print(f"  {ext}: {len(files)} files")
    
    async def test_language_detection(self):
        """Test language detection from filenames and content."""
        results = {'filename_detection': [], 'content_detection': []}
        
        for ext, files in self.sample_files.items():
            for file_path in files:
                filename = os.path.basename(file_path)
                language_from_filename = detect_language_from_filename(filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4096)  # Read first 4KB for detection
                    language_from_content = detect_language_from_content(content)
                except Exception as e:
                    language_from_content = f"ERROR: {str(e)}"
                
                results['filename_detection'].append({
                    'file': file_path,
                    'detected_language': language_from_filename
                })
                
                results['content_detection'].append({
                    'file': file_path,
                    'detected_language': language_from_content
                })
        
        self.results['language_detection'] = results
        return results
    
    async def test_parser_selection(self):
        """Test parser selection and AST generation."""
        results = {'parser_selection': []}
        
        for ext, files in self.sample_files.items():
            for file_path in files:
                filename = os.path.basename(file_path)
                language = detect_language_from_filename(filename)
                
                if not language:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4096)
                    language = detect_language_from_content(content) or "unknown"
                
                try:
                    # Get parser type
                    parser_instance = language_registry.get_parser(language)
                    parser_type = type(parser_instance).__name__ if parser_instance else "None"
                    
                    results['parser_selection'].append({
                        'file': file_path,
                        'language': language,
                        'parser_type': parser_type
                    })
                except Exception as e:
                    results['parser_selection'].append({
                        'file': file_path,
                        'language': language,
                        'parser_type': f"ERROR: {str(e)}"
                    })
        
        self.results['parser_selection'] = results
        return results
    
    async def test_parsing(self):
        """Test parsing a few sample files."""
        results = {'parsing': []}
        
        for ext, files in self.sample_files.items():
            # Only test up to 2 files per extension
            for file_path in files[:2]:
                filename = os.path.basename(file_path)
                language = detect_language_from_filename(filename)
                
                if not language:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4096)
                    language = detect_language_from_content(content) or "unknown"
                
                try:
                    # Get parser
                    parser = language_registry.get_parser(language)
                    
                    if parser:
                        # Read file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Parse file
                        rel_path = get_relative_path(file_path, self.repo_path)
                        parse_result = await parser.parse_async(content, rel_path)
                        
                        # Extract meaningful data from parse result
                        result_summary = {
                            'file': file_path,
                            'language': language,
                            'success': isinstance(parse_result, ParserResult),
                            'has_ast': parse_result.ast is not None if isinstance(parse_result, ParserResult) else False,
                            'features': {
                                'has_blocks': len(parse_result.blocks) > 0 if isinstance(parse_result, ParserResult) else False,
                                'has_imports': len(parse_result.imports) > 0 if isinstance(parse_result, ParserResult) else False,
                                'has_classes': len(parse_result.classes) > 0 if isinstance(parse_result, ParserResult) else False,
                                'has_functions': len(parse_result.functions) > 0 if isinstance(parse_result, ParserResult) else False,
                            }
                        }
                        results['parsing'].append(result_summary)
                    else:
                        results['parsing'].append({
                            'file': file_path,
                            'language': language,
                            'error': 'No parser available'
                        })
                except Exception as e:
                    # Capture traceback for detailed error info
                    tb = traceback.format_exc()
                    results['parsing'].append({
                        'file': file_path,
                        'language': language,
                        'error': str(e),
                        'traceback': tb
                    })
        
        self.results['parsing'] = results
        return results
    
    async def test_database_operations(self):
        """Test storing parsed data in the database."""
        results = {'database': {'postgres': {}, 'neo4j': {}}}
        
        # Store one sample file to test database operations
        for ext, files in self.sample_files.items():
            if files:
                test_file = files[0]
                filename = os.path.basename(test_file)
                rel_path = get_relative_path(test_file, self.repo_path)
                
                language = detect_language_from_filename(filename)
                if not language:
                    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4096)
                    language = detect_language_from_content(content) or "unknown"
                
                try:
                    # Get parser
                    parser = language_registry.get_parser(language)
                    
                    if parser:
                        # Read file
                        with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Parse file
                        parse_result = await parser.parse_async(content, rel_path)
                        
                        if isinstance(parse_result, ParserResult):
                            # Store in PostgreSQL
                            try:
                                # Simplify AST for storage
                                ast_data = {'root': 'simplified_for_test'}
                                
                                # Insert code snippet
                                await query(
                                    "INSERT INTO code_snippets (repo_id, file_path, language, ast, embedding) VALUES (%s, %s, %s, %s, NULL) ON CONFLICT (repo_id, file_path) DO UPDATE SET ast = %s RETURNING id",
                                    (self.repo_id, rel_path, language, json.dumps(ast_data), json.dumps(ast_data))
                                )
                                
                                results['database']['postgres'][ext] = "Success"
                            except Exception as e:
                                results['database']['postgres'][ext] = f"Error: {str(e)}"
                            
                            # Store in Neo4j
                            try:
                                # Get Neo4j connection
                                config = get_connection_config()
                                driver = get_neo4j_driver(config)
                                
                                with driver.session() as session:
                                    # Create file node
                                    file_query = """
                                    MERGE (r:Repository {repo_id: $repo_id})
                                    MERGE (f:File {path: $file_path, repo_id: $repo_id})
                                    MERGE (f)-[:BELONGS_TO]->(r)
                                    RETURN f.path
                                    """
                                    session.run(file_query, repo_id=self.repo_id, file_path=rel_path)
                                    
                                    # Create a code node
                                    if parse_result.functions:
                                        func = parse_result.functions[0]
                                        code_query = """
                                        MATCH (f:File {path: $file_path, repo_id: $repo_id})
                                        MERGE (c:Code {name: $name, type: 'function', repo_id: $repo_id})
                                        MERGE (c)-[:IN_FILE]->(f)
                                        RETURN c.name
                                        """
                                        session.run(
                                            code_query, 
                                            repo_id=self.repo_id, 
                                            file_path=rel_path,
                                            name=func.name
                                        )
                                    
                                driver.close()
                                results['database']['neo4j'][ext] = "Success"
                            except Exception as e:
                                results['database']['neo4j'][ext] = f"Error: {str(e)}"
                        else:
                            results['database']['postgres'][ext] = "Parse result was not valid"
                            results['database']['neo4j'][ext] = "Parse result was not valid"
                    else:
                        results['database']['postgres'][ext] = "No parser available"
                        results['database']['neo4j'][ext] = "No parser available"
                except Exception as e:
                    tb = traceback.format_exc()
                    results['database']['error'] = {'message': str(e), 'traceback': tb}
        
        self.results['database_operations'] = results
        return results
    
    async def test_graph_projection(self):
        """Test graph projection."""
        results = {'graph_projection': {}}
        
        try:
            # Invoke graph projection
            await auto_reinvoke_projection_once(self.repo_id)
            results['graph_projection']['status'] = "Success"
            
            # Verify projection
            config = get_connection_config()
            driver = get_neo4j_driver(config)
            
            with driver.session() as session:
                # Check repository node
                repo_query = """
                MATCH (r:Repository {repo_id: $repo_id})
                RETURN count(r) AS count
                """
                repo_result = session.run(repo_query, repo_id=self.repo_id).single()
                results['graph_projection']['repository_node_exists'] = repo_result['count'] > 0 if repo_result else False
                
                # Check graph projection
                projection_query = """
                CALL gds.graph.exists('repo_graph_' + $repo_id) YIELD exists
                RETURN exists
                """
                try:
                    projection_result = session.run(projection_query, repo_id=str(self.repo_id)).single()
                    results['graph_projection']['projection_exists'] = projection_result['exists'] if projection_result else False
                except Exception:
                    # GDS might not be available
                    results['graph_projection']['projection_exists'] = "GDS plugin error"
            
            driver.close()
        except Exception as e:
            tb = traceback.format_exc()
            results['graph_projection']['error'] = {'message': str(e), 'traceback': tb}
        
        self.results['graph_projection'] = results
        return results
    
    async def test_semantic_search(self):
        """Test semantic search capabilities."""
        results = {'semantic_search': {}}
        
        # Only test if we have embeddings
        try:
            # Test code search
            code_query = "function that parses a file"
            code_results = await search_code(code_query, repo_id=self.repo_id, limit=2)
            results['semantic_search']['code_search'] = {
                'query': code_query,
                'results_count': len(code_results),
                'has_results': len(code_results) > 0
            }
            
            # Test doc search
            doc_query = "documentation about installation"
            doc_results = await search_docs(doc_query, repo_id=self.repo_id, limit=2)
            results['semantic_search']['doc_search'] = {
                'query': doc_query,
                'results_count': len(doc_results),
                'has_results': len(doc_results) > 0
            }
        except Exception as e:
            tb = traceback.format_exc()
            results['semantic_search']['error'] = {'message': str(e), 'traceback': tb}
        
        self.results['semantic_search'] = results
        return results
    
    async def run_all_tests(self):
        """Run all pipeline tests."""
        print("\n=== Starting Pipeline Tests ===\n")
        
        tests = [
            ('Language Detection', self.test_language_detection),
            ('Parser Selection', self.test_parser_selection),
            ('Parsing', self.test_parsing),
            ('Database Operations', self.test_database_operations),
            ('Graph Projection', self.test_graph_projection),
            ('Semantic Search', self.test_semantic_search)
        ]
        
        for name, test_func in tests:
            print(f"\n--- Testing: {name} ---")
            start_time = time.time()
            try:
                result = await test_func()
                duration = time.time() - start_time
                success = 'error' not in str(result).lower()
                status = '✅ Passed' if success else '❌ Failed'
                print(f"{status} in {duration:.2f} seconds")
            except Exception as e:
                duration = time.time() - start_time
                print(f"❌ Error: {e} (after {duration:.2f} seconds)")
                traceback.print_exc()
        
        return self.results
    
    def print_report(self):
        """Print a summary report of all test results."""
        print("\n===== PIPELINE TEST REPORT =====\n")
        
        for component, results in self.results.items():
            status = '✅ Success' if 'error' not in str(results).lower() else '❌ Issues detected'
            print(f"{component}: {status}")
        
        print("\nDetailed results are available in the self.results dictionary.")

async def main_async():
    """Run the pipeline tests asynchronously."""
    if not HAS_IMPORTS:
        print("Error: Required modules could not be imported. Exiting.")
        return
    
    parser = argparse.ArgumentParser(description="Test the RepoAnalyzer pipeline components")
    parser.add_argument("--repo-path", type=str, default=os.getcwd(),
                        help="Path to the repository to analyze")
    parser.add_argument("--clean", action="store_true",
                        help="Clean databases before testing")
    
    args = parser.parse_args()
    
    pipeline_test = PipelineTest(repo_path=args.repo_path, clean_db=args.clean)
    
    try:
        await pipeline_test.setup()
        await pipeline_test.run_all_tests()
        pipeline_test.print_report()
    except Exception as e:
        print(f"Error in pipeline test: {e}")
        traceback.print_exc()
    finally:
        # Clean up
        await close_db_pool()

def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Test interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 