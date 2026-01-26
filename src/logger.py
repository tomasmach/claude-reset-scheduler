import logging
import os
from pathlib import Path

from config import Config


def setup_logging(config: Config) -> logging.Logger:
    log_path = Path(config.log_file).expanduser()

    # Create log directory with secure permissions (0o700 - only owner can read/write/execute)
    # Use umask to set permissions atomically during creation to avoid TOCTOU race
    old_umask = os.umask(0o077)  # Results in 0o700 permissions for newly created directories
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(old_umask)  # Always restore the original umask

    # Attempt to set permissions explicitly (in case directory already existed)
    try:
        stat_info = os.stat(log_path.parent)
        # Only attempt chmod if we own the directory
        if stat_info.st_uid == os.getuid():
            os.chmod(log_path.parent, 0o700)
    except (PermissionError, OSError):
        # Directory may have been created by another process or we lack permissions
        # Don't crash - we can still attempt to create the log file
        pass

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
