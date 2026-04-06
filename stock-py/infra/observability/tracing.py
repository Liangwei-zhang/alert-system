from __future__ import annotations

import logging

_configured = False
logger = logging.getLogger(__name__)


def configure_tracing(service_name: str) -> None:
    global _configured

    if _configured:
        return

    logger.info("Tracing bootstrap enabled for service=%s (no-op backend)", service_name)
    _configured = True
