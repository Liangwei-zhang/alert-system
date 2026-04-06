from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from infra.core.config import get_settings
from infra.core.context import get_request_context


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = get_request_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if context:
            payload["request_id"] = context.request_id
            payload["trace_id"] = context.trace_id
            payload["user_id"] = context.user_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel((level or settings.log_level).upper())

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).propagate = True
