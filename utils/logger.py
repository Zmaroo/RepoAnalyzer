import os
import logging
import sys

def is_logging_disabled() -> bool:
    # Check the environment variable every time log() is called.
    # This ensures that even if DISABLE_LOGGING wasn't set early,
    # subsequent calls will obey it.
    return os.getenv("DISABLE_LOGGING", "False").lower() in ("true", "1", "t")

# If logging is disabled at import time, disable it immediately.
if is_logging_disabled():
    logging.disable(logging.CRITICAL)

# Configure logging with more detailed format for tests
test_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# Create a stream handler that writes to stdout
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(test_formatter)
stream_handler.setLevel(logging.DEBUG)  # Set to DEBUG to catch all messages

# Configure root logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.addHandler(stream_handler)

# Create a specific logger for tree-sitter
tree_sitter_logger = logging.getLogger('tree-sitter')
tree_sitter_logger.setLevel(logging.DEBUG)
tree_sitter_logger.addHandler(stream_handler)

def log(message: str, level: str = "info") -> None:
    if is_logging_disabled():
        return

    if level.lower() == "debug":
        logger.debug(message)
    elif level.lower() == "warning":
        logger.warning(message)
    elif level.lower() == "error":
        logger.error(message)
    else:
        logger.info(message)