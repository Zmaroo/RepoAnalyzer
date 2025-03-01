#!/usr/bin/env python3
"""
Reference Repository Test for RepoAnalyzer

This script tests the ability to clone and analyze a reference repository,
then learn patterns from it to apply to other repositories.
"""

import os
import sys
import asyncio
import subprocess
import argparse
from pathlib import Path

# Import core components for direct API testing
try:
    from index import main_async
    from utils.logger import log
    from db.psql import close_db_pool
except ImportError:
    print("Could not import RepoAnalyzer modules. Running in subprocess mode only.")

# Default reference repository URL (a small, well-structured Python repository)
DEFAULT_REF_REPO = "https://github.com/psf/requests.git"

def run_ref_repo_subprocess(ref_repo_url):
    """Run the reference repository analysis as a subprocess"""
    print(f"Testing reference repository analysis with: {ref_repo_url}")
    
    try:
        # Run the reference repository analysis
        result = subprocess.run(
            ["python", "index.py", "--clone-ref", ref_repo_url], 
            capture_output=True, 
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        # Display results
        print("\nCommand output:")
        print(f"Exit code: {result.returncode}")
        
        if result.stdout:
            print("\nStandard output:")
            print(result.stdout)
        
        if result.stderr:
            print("\nError output:")
            print(result.stderr)
            
        # Check if successful
        if result.returncode == 0:
            print("\n✅ Reference repo analysis passed")
            return True
        else:
            print("\n❌ Reference repo analysis failed - indexer returned error code")
            return False
            
    except Exception as e:
        print(f"\n❌ Error running reference repo analysis: {e}")
        return False

def run_learn_patterns_subprocess(ref_repo_url):
    """Run the learning from reference repository as a subprocess"""
    print(f"Testing learning patterns from reference repository: {ref_repo_url}")
    
    try:
        # Run the pattern learning
        result = subprocess.run(
            ["python", "index.py", "--learn-ref", ref_repo_url], 
            capture_output=True, 
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        # Display results
        print("\nCommand output:")
        print(f"Exit code: {result.returncode}")
        
        if result.stdout:
            print("\nStandard output:")
            print(result.stdout)
        
        if result.stderr:
            print("\nError output:")
            print(result.stderr)
            
        # Check if successful
        if result.returncode == 0:
            print("\n✅ Pattern learning passed")
            return True
        else:
            print("\n❌ Pattern learning failed - returned error code")
            return False
            
    except Exception as e:
        print(f"\n❌ Error running pattern learning: {e}")
        return False

def run_apply_patterns_subprocess():
    """Run the apply patterns to active repository as a subprocess"""
    print("Testing applying learned patterns to active repository")
    
    try:
        # Run the pattern application process
        result = subprocess.run(
            ["python", "index.py", "--apply-ref-patterns"], 
            capture_output=True, 
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        # Display results
        print("\nCommand output:")
        print(f"Exit code: {result.returncode}")
        
        if result.stdout:
            print("\nStandard output:")
            print(result.stdout)
        
        if result.stderr:
            print("\nError output:")
            print(result.stderr)
            
        # Check if successful
        if result.returncode == 0:
            print("\n✅ Pattern application passed")
            return True
        else:
            print("\n❌ Pattern application failed - returned error code")
            return False
            
    except Exception as e:
        print(f"\n❌ Error applying patterns: {e}")
        return False

class Args:
    """Mock args for main_async."""
    
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

async def run_ref_repo_api(ref_repo_url):
    """Run reference repository analysis through API"""
    print(f"Testing reference repository analysis through API: {ref_repo_url}")
    
    try:
        # Create args object for reference repo cloning
        args = Args(clone_ref=ref_repo_url)
        
        # Run the main async function
        log("Starting reference repo analysis through API", level="info")
        await main_async(args)
        
        print("\n✅ API reference repo test passed")
        return True
    except Exception as e:
        print(f"\n❌ Error during API reference repo test: {e}")
        return False
    finally:
        # Ensure database connection is closed
        try:
            await close_db_pool()
        except Exception:
            pass

async def run_learn_patterns_api(ref_repo_url):
    """Run learning patterns through API"""
    print(f"Testing learning patterns through API: {ref_repo_url}")
    
    try:
        # Create args object for learning from reference repo
        args = Args(learn_ref=ref_repo_url)
        
        # Run the main async function
        log("Starting pattern learning through API", level="info")
        await main_async(args)
        
        print("\n✅ API pattern learning test passed")
        return True
    except Exception as e:
        print(f"\n❌ Error during API pattern learning test: {e}")
        return False
    finally:
        # Ensure database connection is closed
        try:
            await close_db_pool()
        except Exception:
            pass

async def run_apply_patterns_api():
    """Run applying patterns through API"""
    print("Testing applying patterns through API")
    
    try:
        # Create args object for applying reference patterns
        args = Args(apply_ref_patterns=True)
        
        # Run the main async function
        log("Starting pattern application through API", level="info")
        await main_async(args)
        
        print("\n✅ API pattern application test passed")
        return True
    except Exception as e:
        print(f"\n❌ Error during API pattern application test: {e}")
        return False
    finally:
        # Ensure database connection is closed
        try:
            await close_db_pool()
        except Exception:
            pass

def main():
    """Main entry point for testing."""
    parser = argparse.ArgumentParser(description="Test reference repository functionality")
    parser.add_argument("--ref-repo", type=str, default=DEFAULT_REF_REPO,
                        help=f"Repository URL to use as reference (default: {DEFAULT_REF_REPO})")
    parser.add_argument("--subprocess-only", action="store_true",
                        help="Only run the subprocess tests, not the API tests")
    parser.add_argument("--api-only", action="store_true",
                        help="Only run the API tests, not the subprocess tests")
    parser.add_argument("--skip-clone", action="store_true",
                        help="Skip cloning step (assume repo already cloned)")
    parser.add_argument("--skip-learn", action="store_true",
                        help="Skip learning step")
    parser.add_argument("--skip-apply", action="store_true",
                        help="Skip applying patterns step")
    
    args = parser.parse_args()
    
    # Track test results
    results = {}
    
    # Run appropriate tests
    if args.subprocess_only or not args.api_only:
        # Subprocess tests
        if not args.skip_clone:
            results["clone_subprocess"] = run_ref_repo_subprocess(args.ref_repo)
        
        if not args.skip_learn:
            results["learn_subprocess"] = run_learn_patterns_subprocess(args.ref_repo)
        
        if not args.skip_apply:
            results["apply_subprocess"] = run_apply_patterns_subprocess()
    
    if args.api_only or not args.subprocess_only:
        # API tests
        try:
            if not args.skip_clone:
                results["clone_api"] = asyncio.run(run_ref_repo_api(args.ref_repo))
            
            if not args.skip_learn:
                results["learn_api"] = asyncio.run(run_learn_patterns_api(args.ref_repo))
            
            if not args.skip_apply:
                results["apply_api"] = asyncio.run(run_apply_patterns_api())
        except Exception as e:
            print(f"Error in API tests: {e}")
    
    # Summarize results
    print("\n" + "=" * 50)
    print("REFERENCE REPOSITORY TEST SUMMARY")
    print("=" * 50)
    
    for test_name, result in results.items():
        print(f"{test_name}: {'✅ PASSED' if result else '❌ FAILED'}")
    
    # Exit with appropriate code
    if False in results.values():
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main() 