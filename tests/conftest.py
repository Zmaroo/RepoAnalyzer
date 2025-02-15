import sys
import os
import pytest
import logging
import faulthandler

# Enable faulthandler for better error reporting
faulthandler.enable()

# Determine the repository root (assumes tests/ is in the repository root)
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Insert the repository root at the beginning of sys.path if it's not already there
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

@pytest.fixture(autouse=True)
def setup_logging():
    # Configure logging for tests
    logging.getLogger().setLevel(logging.DEBUG)
    return None 