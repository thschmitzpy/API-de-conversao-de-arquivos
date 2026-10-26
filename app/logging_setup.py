from __future__ import annotations

import logging
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger


class ConversorJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Os campos do format string ja chegam aqui como None (o LogRecord nao tem esses
        # atributos), entao sao sobrescritos sem checar se a chave existe.

        log_record["timestamp"] = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        if log_record.get("taskName") is None:
            log_record.pop("taskName", None)


def configure_logging(level: int = logging.INFO) -> None:
    formatter = ConversorJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s",
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
