from __future__ import annotations

import logging

from pythonjsonlogger import jsonlogger


class ConversorJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if "timestamp" not in log_record:
            log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name


def configure_logging(level: int = logging.INFO) -> None:
    formatter = ConversorJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "celery",
        "celery.task",
    ):
        lg = logging.getLogger(name)
        for existing in list(lg.handlers):
            lg.removeHandler(existing)
        lg.propagate = True
