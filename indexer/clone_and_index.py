import os
import tempfile
import shutil
import subprocess
from indexer.reference_indexer import index_repository
from utils.logger import log

def clone_and_index_repo(repo_url: str, repo_id: str):
    tmp_dir = tempfile.mkdtemp(prefix=f"repo-{repo_id}-")
    log(f"Cloning {repo_url} into {tmp_dir}")
    try:
        subprocess.run(["git", "clone", repo_url, tmp_dir], check=True)
        index_repository(tmp_dir, repo_id)
    except subprocess.CalledProcessError as e:
        log(f"Error cloning repository: {e}")
    finally:
        shutil.rmtree(tmp_dir)
        log(f"Removed temporary folder: {tmp_dir}")

if __name__ == "__main__":
    # Example usage:
    clone_and_index_repo("https://github.com/samuelcolvin/pydantic.git", "pydantic")