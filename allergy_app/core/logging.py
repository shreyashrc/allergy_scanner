from __future__ import annotations

import logging
import contextvars


class RequestIdFilter(logging.Filter):
    request_id_var = contextvars.ContextVar("request_id", default="-")

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if not hasattr(record, "request_id"):
            try:
                record.request_id = self.request_id_var.get()
            except Exception:
                record.request_id = "-"
        return True


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | rid=%(request_id)s | %(message)s",
    )
    logger = logging.getLogger("allergy_scanner")
    logger.addFilter(RequestIdFilter())
    return logger

