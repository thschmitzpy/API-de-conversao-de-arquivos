from __future__ import annotations

import json
from io import BytesIO

import pytest

from app.workers.processors.csv_validate import validate


def _csv(text: str) -> BytesIO:
    return BytesIO(text.encode("utf-8"))


BASIC_COLUMNS = [
    {"name": "id", "type": "int"},
    {"name": "nome", "type": "string"},
]


def test_report_mode_all_valid():
    csv = _csv("id,nome\n1,alice\n2,bob\n3,carol\n")
    result = validate(csv, {"columns": BASIC_COLUMNS, "mode": "report"})

    assert result.output_content_type == "application/json"
    assert result.output_extension == "json"
    assert result.result_metadata == {
        "total_rows": 3,
        "valid_rows": 3,
        "invalid_rows": 0,
    }
    report = json.loads(result.output.getvalue().decode("utf-8"))
    assert report["errors"] == []


def test_report_mode_records_errors():
    csv = _csv("id,nome\n1,alice\nabc,bob\n3,carol\n")
    result = validate(csv, {"columns": BASIC_COLUMNS, "mode": "report"})

    report = json.loads(result.output.getvalue().decode("utf-8"))
    assert result.result_metadata == {
        "total_rows": 3,
        "valid_rows": 2,
        "invalid_rows": 1,
    }
    assert len(report["errors"]) == 1
    err = report["errors"][0]
    assert err["row"] == 2
    assert err["column"] == "id"
    assert err["value"] == "abc"
    assert isinstance(err["error"], str) and err["error"]


def test_clean_mode_drops_invalid_rows():
    csv = _csv("id,nome\n1,alice\nabc,bob\n3,carol\n")
    result = validate(csv, {"columns": BASIC_COLUMNS, "mode": "clean"})

    assert result.output_content_type == "text/csv"
    assert result.output_extension == "csv"
    assert result.result_metadata["valid_rows"] == 2
    body = result.output.getvalue().decode("utf-8").splitlines()
    assert body[0] == "id,nome"
    assert body[1:] == ["1,alice", "3,carol"]


def test_string_pattern_constraint():
    columns = [
        {"name": "cpf", "type": "string", "pattern": r"^\d{11}$"},
    ]
    csv = _csv("cpf\n12345678901\n123\n")
    result = validate(csv, {"columns": columns, "mode": "report"})

    report = json.loads(result.output.getvalue().decode("utf-8"))
    assert result.result_metadata["valid_rows"] == 1
    assert result.result_metadata["invalid_rows"] == 1
    assert report["errors"][0]["row"] == 2
    assert report["errors"][0]["column"] == "cpf"


def test_numeric_bounds():
    columns = [{"name": "idade", "type": "int", "min": 0, "max": 120}]
    csv = _csv("idade\n30\n-1\n200\n50\n")
    result = validate(csv, {"columns": columns, "mode": "report"})

    assert result.result_metadata == {
        "total_rows": 4,
        "valid_rows": 2,
        "invalid_rows": 2,
    }


def test_date_bounds():
    columns = [
        {
            "name": "data",
            "type": "date",
            "min": "2024-01-01",
            "max": "2024-12-31",
        }
    ]
    csv = _csv("data\n2024-06-15\n2023-12-31\n2025-01-01\n")
    result = validate(csv, {"columns": columns, "mode": "report"})

    assert result.result_metadata == {
        "total_rows": 3,
        "valid_rows": 1,
        "invalid_rows": 2,
    }


def test_optional_column_accepts_empty():
    columns = [
        {"name": "id", "type": "int"},
        {"name": "apelido", "type": "string", "required": False},
    ]
    csv = _csv("id,apelido\n1,ali\n2,\n3,carol\n")
    result = validate(csv, {"columns": columns, "mode": "report"})

    assert result.result_metadata == {
        "total_rows": 3,
        "valid_rows": 3,
        "invalid_rows": 0,
    }


def test_missing_declared_column_raises():
    csv = _csv("id,outro\n1,x\n")
    with pytest.raises(ValueError, match="nome"):
        validate(csv, {"columns": BASIC_COLUMNS, "mode": "report"})


def test_has_header_false_uses_declared_names():
    csv = _csv("1,alice\n2,bob\n")
    result = validate(
        csv,
        {"columns": BASIC_COLUMNS, "mode": "report", "has_header": False},
    )
    assert result.result_metadata == {
        "total_rows": 2,
        "valid_rows": 2,
        "invalid_rows": 0,
    }


def test_invalid_type_raises():
    columns = [{"name": "x", "type": "timestamp"}]
    csv = _csv("x\n1\n")
    with pytest.raises(ValueError, match="tipo"):
        validate(csv, {"columns": columns, "mode": "report"})


def test_pattern_on_non_string_raises():
    columns = [{"name": "id", "type": "int", "pattern": r"\d+"}]
    csv = _csv("id\n1\n")
    with pytest.raises(ValueError, match="pattern"):
        validate(csv, {"columns": columns, "mode": "report"})


def test_min_on_string_raises():
    columns = [{"name": "nome", "type": "string", "min": 1}]
    csv = _csv("nome\nx\n")
    with pytest.raises(ValueError, match="min"):
        validate(csv, {"columns": columns, "mode": "report"})


def test_invalid_mode_raises():
    csv = _csv("id,nome\n1,alice\n")
    with pytest.raises(ValueError, match="mode"):
        validate(csv, {"columns": BASIC_COLUMNS, "mode": "foobar"})


def test_empty_csv_raises():
    csv = _csv("")
    with pytest.raises(ValueError, match="vazio"):
        validate(csv, {"columns": BASIC_COLUMNS, "mode": "report"})


def test_missing_columns_param_raises():
    csv = _csv("id,nome\n1,alice\n")
    with pytest.raises(ValueError, match="columns"):
        validate(csv, {"mode": "report"})


def test_custom_delimiter():
    csv = _csv("id;nome\n1;alice\n2;bob\n")
    result = validate(
        csv,
        {"columns": BASIC_COLUMNS, "mode": "report", "delimiter": ";"},
    )
    assert result.result_metadata == {
        "total_rows": 2,
        "valid_rows": 2,
        "invalid_rows": 0,
    }
