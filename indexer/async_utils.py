import os
import asyncio
from typing import List, Set, Optional, Callable, Awaitable, Any, Dict
import aiofiles
from utils.logger import log
from parsers.types import FileType, ParserResult, ExtractedFeatures
from parsers.models import FileClassification
from functools import wraps
from indexer.common import async_read_file
from utils.error_handling import handle_async_errors, ErrorBoundary, AsyncErrorBoundary
"""[3.0] Asynchronous utilities for file processing.

Flow:
1. Error Handling:
   - Async function decoration
   - Consistent error logging
   - Optional return values

2. File Operations:
   - Async file reading
   - Multiple encoding support
   - Proper resource cleanup

3. Batch Processing:
   - Parallel file processing
   - Progress tracking
   - Resource management
"""


@handle_async_errors
async def async_process_index_file(file_path: str, base_path: str, repo_id:
    int, processor: Any, file_type: FileType) ->None:
    """Asynchronously process and index a file using FileProcessor"""
    with AsyncErrorBoundary(f'processing file {file_path}'):
        await processor.process_file(file_path, repo_id, base_path)


@handle_async_errors
async def batch_process_files(files: List[str], base_path: str, repo_id:
    int, batch_size: int=10, progress_callback: Optional[Callable[[int, int
    ], None]]=None) ->None:
    """[3.3] Enhanced batch processing with progress tracking and error resilience.
    
    Flow:
    1. Initialize processor
    2. Process files in batches
    3. Track progress
    4. Clean up resources
    5. Handle task errors without stopping the entire batch
    """
    with AsyncErrorBoundary(operation_name='batch processing files'):
        from indexer.file_processor import FileProcessor
        processor = FileProcessor()
        total_files = len(files)
        processed = 0
        errors = 0
        try:
            for i in range(0, total_files, batch_size):
                batch = files[i:i + batch_size]
                tasks = []
                for f in batch:
                    task = asyncio.create_task(async_process_index_file(
                        file_path=f, base_path=base_path, repo_id=repo_id,
                        processor=processor, file_type=FileType.CODE))
                    tasks.append(task)
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        log(f'Error in batch processing: {result}', level=
                            'error')
                        errors += 1
                processed += len(batch)
                if progress_callback:
                    progress_callback(processed, total_files)
                await asyncio.sleep(0)
            log(f'Batch processing completed: {processed} files processed, {errors} errors'
                , level='info' if errors == 0 else 'warning')
        except asyncio.CancelledError:
            log('Batch processing cancelled', level='warning')
            for task in asyncio.all_tasks():
                if task != asyncio.current_task():
                    task.cancel()
            raise
        except Exception as e:
            log(f'Unexpected error in batch processing: {e}', level='error')
            raise
        finally:
            processor.clear_cache()
