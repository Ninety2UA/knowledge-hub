"""Structured JSON logging configuration for Cloud Run.

Configures Python stdlib logging to emit JSON with GCP-compatible field names.
Cloud Run auto-extracts `severity`, `message`, and other fields from JSON on stdout.

Usage:
    from knowledge_hub.logging_config import configure_logging
    configure_logging()
"""

import logging
import logging.config

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(funcName)s %(message)s",
            "rename_fields": {
                "levelname": "severity",
                "asctime": "timestamp",
                "name": "logger",
            },
            "static_fields": {
                "service": "knowledge-hub",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def configure_logging() -> None:
    """Apply structured JSON logging configuration.

    Call once at application startup (e.g., in FastAPI lifespan).
    All subsequent ``logging.getLogger()`` calls will emit JSON to stdout
    with GCP-compatible ``severity`` field mapped from Python's ``levelname``.
    """
    logging.config.dictConfig(LOGGING_CONFIG)
