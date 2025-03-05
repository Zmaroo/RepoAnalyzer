"""Utility script to clear various cache files before running tests."""
# python -m tests.clear_cache_utils

# Or from Python code:
# from tests.clear_cache_utils import clear_cache_files
# clear_cache_files()

import os
import shutil
import asyncio
from typing import List
from pathlib import Path
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent

def find_cache_directories(start_path: Path) -> List[Path]:
    """Find all cache directories in the project."""
    cache_dirs = []
    for root, dirs, _ in os.walk(start_path):
        # Skip .git directory
        if '.git' in dirs:
            dirs.remove('.git')
            
        # Find cache directories
        for dir_name in dirs:
            if (dir_name == '__pycache__' or 
                dir_name.endswith('.egg-info') or 
                dir_name == '.pytest_cache' or 
                dir_name == '.coverage' or
                dir_name == 'test_outputs'):
                cache_dirs.append(Path(root) / dir_name)
    return cache_dirs

@handle_async_errors
async def clear_cache_files(directory: Path = None) -> None:
    """
    Clear all cache files and directories.
    
    Args:
        directory: Optional specific directory to clean, defaults to project root
    """
    if directory is None:
        directory = get_project_root()
    
    async with AsyncErrorBoundary("clearing cache files"):
        try:
            # Find all cache directories
            cache_dirs = find_cache_directories(directory)
            
            # Remove each cache directory
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    log(f"Removing cache directory: {cache_dir}")
                    shutil.rmtree(cache_dir)
            
            # Remove .pyc files that might be outside __pycache__
            for pyc_file in directory.rglob("*.pyc"):
                log(f"Removing .pyc file: {pyc_file}")
                pyc_file.unlink()
                
            # Remove .coverage files
            for coverage_file in directory.rglob(".coverage"):
                log(f"Removing coverage file: {coverage_file}")
                coverage_file.unlink()
                
            log("Cache clearing completed successfully.")
            
        except Exception as e:
            log(f"Error while clearing cache: {e}", level="error")
            raise

async def main_async():
    """Async main entry point."""
    await clear_cache_files()

def main():
    """Main entry point."""
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        log("Cache clearing interrupted by user", level="info")
    except Exception as e:
        log(f"Error during cache clearing: {e}", level="error")
        raise

if __name__ == "__main__":
    main() 