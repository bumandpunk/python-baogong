# -*- coding: utf-8 -*-
"""Logging utilities"""
import json
import logging
import sys
from pathlib import Path

from ..config import LOG_LEVEL, LOG_FORMAT, LOG_FILE, SEND_AUDIT_LOG_FILE


def _ensure_parent_dir(file_path: str) -> None:
    """Create log file parent directory when needed."""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(stream_handler)

        _ensure_parent_dir(LOG_FILE)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(file_handler)
        logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False

    return logger


def get_send_audit_logger() -> logging.Logger:
    """Get dedicated structured logger for send audit records."""
    logger = logging.getLogger("wx4py.send_audit")

    if not logger.handlers:
        _ensure_parent_dir(SEND_AUDIT_LOG_FILE)
        file_handler = logging.FileHandler(SEND_AUDIT_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger


def log_send_audit(payload: dict) -> None:
    """Write one structured send audit record as JSONL."""
    get_send_audit_logger().info(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
