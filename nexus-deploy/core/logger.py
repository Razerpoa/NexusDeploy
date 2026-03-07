import logging
import sys
from pathlib import Path

# Log to the current directory where the command is run
LOG_FILE = Path.cwd() / "nexus-error.log"

def setup_logger():
    logger = logging.getLogger("nexus")
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler (logs everything)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Stream handler (logs only ERROR/CRITICAL to stderr)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.ERROR)
    stream_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    
    return logger

logger = setup_logger()
