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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

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