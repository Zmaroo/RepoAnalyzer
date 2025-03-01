#!/usr/bin/env python3
"""
Enhanced System Test for RepoAnalyzer

This script tests the full indexing pipeline of the RepoAnalyzer system by:
1. Running basic indexing
2. Verifying database records were created
3. Checking that language detection works
4. Ensuring the graph projection was created
"""

import os
import sys
import asyncio
import subprocess
import argparse
from pathlib import Path
import json
import time

# Import core components for direct API testing
try:
    from index import main_async
    from utils.logger import log
    from db.psql import close_db_pool, query
    from db.neo4j_ops import get_neo4j_driver, get_connection_config
    from parsers.language_mapping import get_supported_languages
    from indexer.file_utils import get_files
except ImportError:
    print("Could not import RepoAnalyzer modules. Running in subprocess mode only.")

def run_indexer_subprocess():
    """Run the indexer as a subprocess and capture output"""
    print("Testing RepoAnalyzer with subprocess call to: python index.py --index")
    
    start_time = time.time()
    
    try:
        # Run the indexer on the current repository
        result = subprocess.run(
            ["python", "index.py", "--index"], 
            capture_output=True, 
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Display results
        print("\nCommand output:")
        print(f"Exit code: {result.returncode}")
        print(f"Duration: {duration:.2f} seconds")
        
        if result.stdout:
            print("\nStandard output:")
            print(result.stdout)
        
        if result.stderr:
            print("\nError output:")
            print(result.stderr)
            
        # Check if successful
        if result.returncode == 0:
            print("\n✅ Subprocess test passed - indexer ran successfully")
            return True
        else:
            print("\n❌ Subprocess test failed - indexer returned error code")
            return False
            
    except Exception as e:
        print(f"\n❌ Error running subprocess: {e}")
        return False

class Args:
    """Mock args for main_async testing."""
    
    def __init__(self, **kwargs):
        self.clean = kwargs.get('clean', False)
        self.index = kwargs.get('index', os.getcwd())
        self.clone_ref = kwargs.get('clone_ref', None)
        self.share_docs = kwargs.get('share_docs', None)
        self.search_docs = kwargs.get('search_docs', None)
        self.watch = kwargs.get('watch', False)
        self.learn_ref = kwargs.get('learn_ref', None)
        self.multi_ref = kwargs.get('multi_ref', None)
        self.apply_ref_patterns = kwargs.get('apply_ref_patterns', False)
        self.deep_learning = kwargs.get('deep_learning', False)

async def verify_postgres_data(repo_id):
    """Verify data was properly stored in PostgreSQL"""
    results = {}
    
    # Check repository record
    repo_data = await query("SELECT * FROM repositories WHERE id = %s", (repo_id,))
    results['repository_exists'] = len(repo_data) > 0
    
    # Check code snippets
    code_count = await query("SELECT COUNT(*) FROM code_snippets WHERE repo_id = %s", (repo_id,))
    results['code_snippets_count'] = code_count[0]['count'] if code_count else 0
    
    # Check documents
    doc_count = await query("SELECT COUNT(*) FROM repo_docs WHERE repo_id = %s", (repo_id,))
    results['docs_count'] = doc_count[0]['count'] if doc_count else 0
    
    return results

def verify_neo4j_data(repo_id):
    """Verify data was properly stored in Neo4j"""
    results = {}
    
    try:
        # Get Neo4j connection
        config = get_connection_config()
        driver = get_neo4j_driver(config)
        
        with driver.session() as session:
            # Check repository node
            repo_query = """
            MATCH (r:Repository {repo_id: $repo_id})
            RETURN count(r) AS count
            """
            repo_result = session.run(repo_query, repo_id=repo_id).single()
            results['repository_node_exists'] = repo_result['count'] > 0 if repo_result else False
            
            # Check file nodes
            file_query = """
            MATCH (f:File)-[:BELONGS_TO]->(r:Repository {repo_id: $repo_id})
            RETURN count(f) AS count
            """
            file_result = session.run(file_query, repo_id=repo_id).single()
            results['file_nodes_count'] = file_result['count'] if file_result else 0
            
            # Check code nodes
            code_query = """
            MATCH (c:Code)-[:IN_FILE]->()-[:BELONGS_TO]->(r:Repository {repo_id: $repo_id})
            RETURN count(c) AS count
            """
            code_result = session.run(code_query, repo_id=repo_id).single()
            results['code_nodes_count'] = code_result['count'] if code_result else 0
        
        driver.close()
    except Exception as e:
        print(f"Error verifying Neo4j data: {e}")
        results['error'] = str(e)
    
    return results

def check_language_detection():
    """Verify that language detection is working"""
    results = {}
    
    # Get supported languages
    supported_languages = get_supported_languages()
    results['supported_languages_count'] = len(supported_languages)
    
    # Count files by extension in the current repo
    file_extensions = {}
    try:
        files = get_files(os.getcwd())
        for file_path in files:
            _, ext = os.path.splitext(file_path)
            if ext:
                if ext not in file_extensions:
                    file_extensions[ext] = 0
                file_extensions[ext] += 1
        results['extensions_found'] = file_extensions
    except Exception as e:
        print(f"Error checking files: {e}")
        results['error'] = str(e)
    
    return results

async def run_indexer_api():
    """Run the indexer directly through its API and verify results"""
    print("Testing RepoAnalyzer through direct API call with verification")
    
    start_time = time.time()
    repo_id = None
    
    try:
        # Create args object with clean database to ensure fresh state
        args = Args(clean=True)
        
        # Run the main async function
        log("Starting RepoAnalyzer through API", level="info")
        await main_async(args)
        
        end_time = time.time()
        duration = end_time - start_time
        print(f"Indexing completed in {duration:.2f} seconds")
        
        # Verify results
        print("\nVerifying indexed data...")
        
        # Get repository ID
        repo_result = await query("SELECT id FROM repositories WHERE repo_type = 'active' ORDER BY id DESC LIMIT 1")
        if repo_result:
            repo_id = repo_result[0]['id']
            print(f"Repository ID: {repo_id}")
            
            # Verify PostgreSQL data
            pg_results = await verify_postgres_data(repo_id)
            print("\nPostgreSQL verification:")
            for key, value in pg_results.items():
                print(f"  {key}: {value}")
            
            # Verify Neo4j data
            neo4j_results = verify_neo4j_data(repo_id)
            print("\nNeo4j verification:")
            for key, value in neo4j_results.items():
                print(f"  {key}: {value}")
            
            # Check language detection
            lang_results = check_language_detection()
            print("\nLanguage detection verification:")
            print(f"  Supported languages: {lang_results['supported_languages_count']}")
            if 'extensions_found' in lang_results:
                print("  Extensions found in repository:")
                for ext, count in lang_results['extensions_found'].items():
                    print(f"    {ext}: {count} files")
            
            # Determine success based on verification results
            success = (
                pg_results.get('repository_exists', False) and
                pg_results.get('code_snippets_count', 0) > 0 and
                neo4j_results.get('repository_node_exists', False) and
                neo4j_results.get('file_nodes_count', 0) > 0
            )
            
            if success:
                print("\n✅ API test passed - indexer ran successfully and data verified")
                return True
            else:
                print("\n❌ API test failed - data verification failed")
                return False
        else:
            print("\n❌ API test failed - no repository found in database")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during API test: {e}")
        return False
    finally:
        # Ensure database connection is closed
        try:
            await close_db_pool()
        except Exception:
            pass

def main():
    """Main entry point for testing."""
    parser = argparse.ArgumentParser(description="Test the RepoAnalyzer system")
    parser.add_argument("--subprocess-only", action="store_true",
                        help="Only run the subprocess test, not the API test")
    parser.add_argument("--api-only", action="store_true",
                        help="Only run the API test, not the subprocess test")
    parser.add_argument("--skip-verification", action="store_true",
                        help="Skip data verification after indexing (faster)")
    
    args = parser.parse_args()
    
    # Track test results
    subprocess_result = None
    api_result = None
    
    # Run appropriate tests
    if args.api_only:
        try:
            api_result = asyncio.run(run_indexer_api())
        except Exception as e:
            print(f"Error in API test: {e}")
            api_result = False
    elif args.subprocess_only:
        subprocess_result = run_indexer_subprocess()
    else:
        # Run both tests
        subprocess_result = run_indexer_subprocess()
        
        print("\n" + "-" * 50 + "\n")
        
        try:
            api_result = asyncio.run(run_indexer_api())
        except Exception as e:
            print(f"Error in API test: {e}")
            api_result = False
    
    # Summarize results
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    if subprocess_result is not None:
        print(f"Subprocess test: {'✅ PASSED' if subprocess_result else '❌ FAILED'}")
    
    if api_result is not None:
        print(f"API test: {'✅ PASSED' if api_result else '❌ FAILED'}")
    
    # Exit with appropriate code
    if (subprocess_result is False) or (api_result is False):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main() 