import logging
import os
from pathlib import Path

from config import Config


def setup_logging(config: Config) -> logging.Logger:
    log_path = Path(config.log_file).expanduser()

    # Create log directory with secure permissions (0o700 - only owner can read/write/execute)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(log_path.parent, 0o700)

    logger = logging.getLogger("claude_reset_scheduler")
    logger.setLevel(getattr(logging, config.log_level))

    if logger.handlers:
        logger.handlers.clear()

    handler = logging.FileHandler(log_path)
    handler.setLevel(getattr(logging, config.log_level))

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Set secure permissions for log file (0o600 - only owner can read/write)
    if log_path.exists():
        os.chmod(log_path, 0o600)

    return logger
