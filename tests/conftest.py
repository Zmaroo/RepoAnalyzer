import sys
import os

# Determine the repository root (assumes tests/ is in the repository root)
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Insert the repository root at the beginning of sys.path if it's not already there
if repo_root not in sys.path:
    sys.path.insert(0, repo_root) 