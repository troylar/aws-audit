"""Logging configuration for AWS Baseline Snapshot tool."""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, verbose: bool = False) -> None:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARN, ERROR)
        log_file: Optional log file path
        verbose: If True, show detailed logs; if False, suppress all but critical
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # In non-verbose mode, suppress all logs except CRITICAL
    # User will only see styled Rich console output
    if not verbose:
        numeric_level = logging.CRITICAL

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (only add if verbose or log_file specified)
    if verbose or log_file:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("boto3").setLevel(logging.CRITICAL)
    logging.getLogger("botocore").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    logging.getLogger("s3transfer").setLevel(logging.CRITICAL)

    # Suppress internal module logs unless verbose
    if not verbose:
        logging.getLogger("src").setLevel(logging.CRITICAL)
        logging.getLogger("src.snapshot").setLevel(logging.CRITICAL)
        logging.getLogger("src.snapshot.resource_collectors").setLevel(logging.CRITICAL)
        logging.getLogger("src.snapshot.capturer").setLevel(logging.CRITICAL)
        logging.getLogger("src.snapshot.storage").setLevel(logging.CRITICAL)
        logging.getLogger("src.aws").setLevel(logging.CRITICAL)
        logging.getLogger("src.aws.credentials").setLevel(logging.CRITICAL)
