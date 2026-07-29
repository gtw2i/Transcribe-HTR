# logging_config.py
"""
Centralized logging configuration for Streamlit Transcribe app.

Provides structured logging with configurable levels and outputs.
Keeps application logs separate from user-facing messages.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Import config for logging settings
from config import DEBUG_MODE, LOG_FORCE_FLUSH

# =========================
# LOGGING CONFIGURATION
# =========================

# Logging settings (can be overridden by environment variables)
LOG_LEVEL = os.getenv("STREAMLIT_TRANSCRIBE_LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = os.getenv("STREAMLIT_TRANSCRIBE_LOG_TO_FILE", "true").lower() == "true"
LOG_TO_CONSOLE = (
    os.getenv("STREAMLIT_TRANSCRIBE_LOG_TO_CONSOLE", "false").lower() == "true"
)
LOG_DIRECTORY = Path(os.getenv("STREAMLIT_TRANSCRIBE_LOG_DIR", "logs"))
LOG_FORCE_FLUSH_ENV = (
    os.getenv("STREAMLIT_TRANSCRIBE_LOG_FORCE_FLUSH", str(LOG_FORCE_FLUSH)).lower()
    == "true"
)

# Enable debug logging if DEBUG_MODE is True
if DEBUG_MODE:
    LOG_LEVEL = "DEBUG"
    LOG_TO_CONSOLE = True

# Create logs directory if it doesn't exist
if LOG_TO_FILE:
    LOG_DIRECTORY.mkdir(exist_ok=True)


# =========================
# LOGGER SETUP
# =========================


def setup_logger(name: str = "streamlit_transcribe") -> logging.Logger:
    """
    Set up a logger with configurable handlers.

    Args:
        name: Logger name (typically module name)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Set logging level
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    if LOG_TO_FILE:
        try:
            log_file = (
                LOG_DIRECTORY
                / f"streamlit_transcribe_{datetime.now().strftime('%Y%m%d')}.log"
            )
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            # Force immediate flushing for real-time logging
            file_handler.flush = lambda: (
                file_handler.stream.flush() if hasattr(file_handler, "stream") else None
            )
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create file handler: {e}", file=sys.stderr)

    # Console handler (only if explicitly enabled)
    if LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        # Force immediate flushing for real-time console output
        console_handler.flush = lambda: (
            console_handler.stream.flush()
            if hasattr(console_handler, "stream")
            else None
        )
        logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger


# =========================
# CONVENIENCE FUNCTIONS
# =========================

# Create default logger instance
_default_logger = setup_logger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to calling module)

    Returns:
        Logger instance
    """
    if name is None:
        return _default_logger
    return setup_logger(name)


def log_debug(message: str, **kwargs):
    """Log a debug message."""
    _default_logger.debug(_format_message(message, kwargs))
    _flush_handlers(_default_logger)


def log_info(message: str, **kwargs):
    """Log an info message."""
    _default_logger.info(_format_message(message, kwargs))
    _flush_handlers(_default_logger)


def log_warning(message: str, **kwargs):
    """Log a warning message."""
    _default_logger.warning(_format_message(message, kwargs))
    _flush_handlers(_default_logger)


def log_error(message: str, **kwargs):
    """Log an error message."""
    _default_logger.error(_format_message(message, kwargs))
    _flush_handlers(_default_logger)


def log_exception(message: str, **kwargs):
    """Log an exception with traceback."""
    _default_logger.exception(_format_message(message, kwargs))
    _flush_handlers(_default_logger)


_SENSITIVE_KEYS = frozenset({"openai_api_key", "gemini_api_key", "token", "password"})


def _format_message(message: str, kwargs: Dict[str, Any]) -> str:
    """Format log message with additional context. Sensitive keys are redacted."""
    if kwargs:
        parts = [
            f"{k}=[REDACTED]" if k in _SENSITIVE_KEYS else f"{k}={v}"
            for k, v in kwargs.items()
        ]
        return f"{message} | {' | '.join(parts)}"
    return message


def _flush_handlers(logger: logging.Logger) -> None:
    """Force flush all handlers for immediate output."""
    if not LOG_FORCE_FLUSH_ENV:
        return

    for handler in logger.handlers:
        try:
            if hasattr(handler, "flush"):
                handler.flush()
            if hasattr(handler, "stream") and hasattr(handler.stream, "flush"):
                handler.stream.flush()
        except Exception:
            # Ignore flush errors to prevent breaking the application
            pass


# =========================
# AUDIT LOGGING
# =========================


class AuditLogger:
    """Specialized logger for audit events and user actions."""

    def __init__(self):
        self.logger = setup_logger("audit")

    def log_file_upload(self, filename: str, file_size: int, user_session: str):
        """Log file upload event."""
        self.logger.info(
            "File uploaded",
            extra={
                "event_type": "file_upload",
                "upload_filename": filename,
                "file_size": file_size,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_transcription_start(self, model: str, n_responses: int, user_session: str):
        """Log transcription start event."""
        self.logger.info(
            "Transcription started",
            extra={
                "event_type": "transcription_start",
                "model": model,
                "n_responses": n_responses,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_transcription_complete(
        self, model: str, tokens_used: int, success: bool, user_session: str
    ):
        """Log transcription completion event."""
        self.logger.info(
            "Transcription completed",
            extra={
                "event_type": "transcription_complete",
                "model": model,
                "tokens_used": tokens_used,
                "success": success,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_export(self, export_type: str, file_count: int, user_session: str):
        """Log export event."""
        self.logger.info(
            "Export generated",
            extra={
                "event_type": "export",
                "export_type": export_type,
                "file_count": file_count,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_json_load(self, json_path: str, user_session: str):
        """Log JSON file load operation."""
        self.logger.info(
            "JSON file loaded",
            extra={
                "event_type": "json_load",
                "json_path": json_path,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_json_save(self, json_path: str, user_session: str):
        """Log JSON file save operation."""
        self.logger.info(
            "JSON file saved",
            extra={
                "event_type": "json_save",
                "json_path": json_path,
                "session_id": user_session,
            },
        )
        _flush_handlers(self.logger)

    def log_error_event(
        self, error_type: str, error_message: str, user_session: str, **context
    ):
        """Log error event with context."""
        self.logger.error(
            f"Error occurred: {error_type}",
            extra={
                "event_type": "error",
                "error_type": error_type,
                "error_message": error_message,
                "session_id": user_session,
                **context,
            },
        )
        _flush_handlers(self.logger)


# Create audit logger instance
audit_logger = AuditLogger()


# =========================
# INITIALIZATION
# =========================


def init_logging():
    """Initialize logging system. Call this at app startup."""
    logger = get_logger()
    log_info(
        "Logging system initialized",
        log_level=LOG_LEVEL,
        log_to_file=LOG_TO_FILE,
        log_to_console=LOG_TO_CONSOLE,
    )

    if LOG_TO_FILE:
        log_info(
            "Log files will be written to", directory=str(LOG_DIRECTORY.absolute())
        )


# Initialize logging when module is imported
init_logging()
