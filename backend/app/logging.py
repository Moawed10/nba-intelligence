import json
import logging
import sys
from datetime import UTC, datetime

from app.config import get_settings

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stderr)
    plain = logging.Formatter("%(levelname)s %(name)s %(message)s")
    handler.setFormatter(JsonFormatter() if settings.log_json else plain)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level)
