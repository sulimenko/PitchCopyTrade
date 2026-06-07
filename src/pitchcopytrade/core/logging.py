from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from pitchcopytrade.core.config import LoggingSettings


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: LoggingSettings) -> None:
    root_logger = logging.getLogger()
    level = getattr(logging, settings.level, logging.INFO)
    root_logger.setLevel(level)

    root_logger.handlers.clear()

    if settings.json_logs:
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    if settings.file_path:
        file_handler = logging.FileHandler(settings.file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
