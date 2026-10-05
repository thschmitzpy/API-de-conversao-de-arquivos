from __future__ import annotations

import io
import json
import logging

import pytest

from app.logging_setup import configure_logging


@pytest.fixture
def capture_json(monkeypatch):
    configure_logging()
    buffer = io.StringIO()
    handler = logging.getLogger().handlers[0]
    monkeypatch.setattr(handler, "stream", buffer)
    yield buffer


def _parse(buffer: io.StringIO) -> list[dict]:
    buffer.seek(0)
    return [json.loads(line) for line in buffer.read().splitlines() if line.strip()]


def test_output_e_json_valido_com_campos_base(capture_json):
    logging.getLogger("teste").info("ola mundo")

    records = _parse(capture_json)

    assert len(records) == 1
    rec = records[0]
    assert rec["message"] == "ola mundo"
    assert rec["level"] == "INFO"
    assert rec["logger"] == "teste"
    assert "timestamp" in rec


def test_extra_vira_campo_toplevel(capture_json):
    logging.getLogger("teste").info(
        "job concluido",
        extra={"job_id": "abc-123", "operation": "image.thumbnail"},
    )

    rec = _parse(capture_json)[0]

    assert rec["job_id"] == "abc-123"
    assert rec["operation"] == "image.thumbnail"
    assert rec["message"] == "job concluido"


def test_exception_inclui_stacktrace(capture_json):
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("teste").exception("deu erro", extra={"job_id": "x"})

    rec = _parse(capture_json)[0]

    assert "ValueError" in rec["exc_info"]
    assert "boom" in rec["exc_info"]
    assert rec["job_id"] == "x"


def test_uvicorn_access_usa_mesmo_formatter(capture_json):
    logging.getLogger("uvicorn.access").info("GET /health 200")

    records = _parse(capture_json)

    assert len(records) == 1
    assert records[0]["logger"] == "uvicorn.access"
    assert records[0]["message"] == "GET /health 200"
