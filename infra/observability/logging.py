"""
structlog — JSON in production, human-readable locally.

Two rules:
  1. NEVER log excerpt text, executive names, or API keys. Logs are the
     easiest place for personal data to leak out of the retention policy.
  2. Every log line carries request_id where one exists, so a single request
     can be traced across API and worker.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

REDACT_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "shred_master_key",
    "clerk_secret_key",
    "excerpt",
    "excerpt_text",
    "exec_name",
    "subject_name",
    "narrative_md",
}


def _redact(logger, method_name, event_dict):
    for k in list(event_dict):
        if k.lower() in REDACT_KEYS:
            event_dict[k] = "[redacted]"
    return event_dict


def _add_request_id(logger, method_name, event_dict):
    rid = request_id_ctx.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(json_output: bool = True, level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper())
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        _redact,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "troy"):
    return structlog.get_logger(name)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:16]
    request_id_ctx.set(rid)
    return rid
