"""
Logger configuration for SecurePythonUpgradeProject.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "bini",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    verbose: bool = False
) -> logging.Logger:
    """
    Setup and configure logger.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional file to log to
        verbose: Enable verbose output

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    # Remove existing handlers
    logger.handlers.clear()

    # Set level
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "bini") -> logging.Logger:
    """
    Get existing logger or create new one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
