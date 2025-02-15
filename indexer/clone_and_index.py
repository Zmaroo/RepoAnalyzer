import os
import tempfile
import shutil
import subprocess
from utils.logger import log
from db.psql import query
from indexer.async_indexer import async_index_code, async_index_docs
import asyncio

def get_or_create_repo(repo_name: str, source_url: str = None, repo_type: str = "active", active_repo_id: int | None = None) -> int:
    """
    Retrieves the repository ID by its unique repository name.
    If the repository doesn't exist, it will be created with the given type
    ('active' or 'reference') and associated active_repo_id if applicable.
    """
    result = query("SELECT id FROM repositories WHERE repo_name = %s;", (repo_name,))
    if result:
        return result[0]["id"]

    insert_sql = """
        INSERT INTO repositories (repo_name, source_url, repo_type, active_repo_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """
    result = query(insert_sql, (repo_name, source_url, repo_type, active_repo_id))
    return result[0]["id"]

def clone_and_index_repo(repo_url: str, repo_name: str | None = None, active_repo_id: int | None = None):
    """
    Clones a reference repository into a temporary directory, indexes its files asynchronously,
    and then deletes the temp folder. For reference repos, active_repo_id is passed so that
    the repository is associated with the given active project.
    """
    if repo_name is None:
        repo_name = repo_url.split('/')[-1].replace('.git', '')
    # Create a repository entry with type "reference" and associate it with the active repo.
    repo_id = get_or_create_repo(repo_name, repo_url, repo_type="reference", active_repo_id=active_repo_id)

    tmp_dir = tempfile.mkdtemp(prefix=f"repo-{repo_id}-")
    log(f"🔄 Cloning {repo_url} into {tmp_dir}")
    try:
        subprocess.run(["git", "clone", repo_url, tmp_dir], check=True)
        from indexer.async_indexer import async_index_repository
        from utils.async_runner import submit_async_task
        future = submit_async_task(async_index_repository(tmp_dir, repo_id))
        # Wait for asynchronous indexing to complete before cleanup
        future.result()
    except subprocess.CalledProcessError as e:
        log(f"❌ Error cloning repository: {e}", level="error")
    finally:
        shutil.rmtree(tmp_dir)
        log(f"🧹 Removed temporary folder: {tmp_dir}")

def index_active_project():
    """
    Initiates asynchronous indexing for the active project.
    Uses the new async_index_code and async_index_docs functions
    to index source code and documentation respectively.
    """
    repository_id = get_or_create_repo("active")
    base_path = "./active_project"  # Update this path as needed

    loop = asyncio.get_event_loop()
    tasks = [
        async_index_code(repository_id, base_path),
        async_index_docs(repository_id, base_path)
    ]
    loop.run_until_complete(asyncio.gather(*tasks))
    log("Active project indexing completed.")

if __name__ == "__main__":
    # Index the current active project
    index_active_project()
    
    # Example: Index a reference repository (comment out if not needed)
    # clone_and_index_repo("https://github.com/samuelcolvin/pydantic.git", "pydantic")