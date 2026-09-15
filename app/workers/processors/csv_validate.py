from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from pydantic import Field, ValidationError, create_model

from app.workers.processors.base import ProcessorResult

_TYPE_MAP: dict[str, type] = {
    "string": str,
    "int": int,
    "float": float,
    "bool": bool,
    "date": date,
}
_NUMERIC_LIKE = {"int", "float", "date"}


def validate(
    input_stream: BytesIO,
    parameters: dict[str, Any],
) -> ProcessorResult:
    columns = parameters.get("columns")
    if not columns or not isinstance(columns, list):
        raise ValueError("parameters deve conter 'columns' (lista nao vazia)")

    delimiter = parameters.get("delimiter", ",")
    has_header = bool(parameters.get("has_header", True))
    encoding = parameters.get("encoding", "utf-8")
    mode = parameters.get("mode", "report")
    if mode not in ("report", "clean"):
        raise ValueError(f"mode invalido: '{mode}' (use 'report' ou 'clean')")

    declared_names = [c["name"] for c in columns]

    try:
        df = pd.read_csv(
            input_stream,
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            encoding=encoding,
            header=0 if has_header else None,
            names=None if has_header else declared_names,
        )
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV vazio ou sem conteudo") from exc

    if has_header:
        missing = [name for name in declared_names if name not in df.columns]
        if missing:
            raise ValueError(f"colunas declaradas ausentes no CSV: {missing}")
        df = df[declared_names]

    row_model = _build_row_model(columns)

    total_rows = len(df)
    errors: list[dict[str, Any]] = []
    valid_records: list[dict[str, Any]] = []
    invalid_rows: set[int] = set()

    for idx, record in enumerate(df.to_dict(orient="records"), start=1):
        clean = {
            k: (None if isinstance(v, float) and pd.isna(v) else v)
            for k, v in record.items()
        }
        try:
            model = row_model(**clean)
        except ValidationError as ve:
            invalid_rows.add(idx)
            for err in ve.errors():
                column = err["loc"][0] if err["loc"] else None
                errors.append(
                    {
                        "row": idx,
                        "column": column,
                        "value": clean.get(column) if column else None,
                        "error": err["msg"],
                    }
                )
        else:
            if mode == "clean":
                valid_records.append(model.model_dump(mode="json"))

    valid_count = total_rows - len(invalid_rows)
    metadata = {
        "total_rows": total_rows,
        "valid_rows": valid_count,
        "invalid_rows": len(invalid_rows),
    }

    if mode == "report":
        report = {**metadata, "errors": errors}
        payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        buf = BytesIO(payload.encode("utf-8"))
        return ProcessorResult(
            output=buf,
            output_content_type="application/json",
            output_extension="json",
            result_metadata=metadata,
        )

    out_df = pd.DataFrame(valid_records, columns=declared_names)
    buf = BytesIO()
    out_df.to_csv(buf, index=False, sep=delimiter)
    buf.seek(0)
    return ProcessorResult(
        output=buf,
        output_content_type="text/csv",
        output_extension="csv",
        result_metadata=metadata,
    )


def _build_row_model(columns: list[dict[str, Any]]):
    fields: dict[str, tuple[Any, Any]] = {}
    for col in columns:
        name = col.get("name")
        if not name:
            raise ValueError("coluna sem 'name'")
        col_type = col.get("type")
        if col_type not in _TYPE_MAP:
            raise ValueError(
                f"coluna '{name}': tipo '{col_type}' invalido "
                f"(use string/int/float/bool/date)"
            )
        py_type = _TYPE_MAP[col_type]

        constraints: dict[str, Any] = {}
        if "pattern" in col:
            if col_type != "string":
                raise ValueError(
                    f"coluna '{name}': 'pattern' aplicavel apenas a type=string"
                )
            constraints["pattern"] = col["pattern"]
        if "min" in col:
            if col_type not in _NUMERIC_LIKE:
                raise ValueError(
                    f"coluna '{name}': 'min' aplicavel apenas a int/float/date"
                )
            constraints["ge"] = _coerce_bound(col_type, col["min"])
        if "max" in col:
            if col_type not in _NUMERIC_LIKE:
                raise ValueError(
                    f"coluna '{name}': 'max' aplicavel apenas a int/float/date"
                )
            constraints["le"] = _coerce_bound(col_type, col["max"])

        required = col.get("required", True)
        if required:
            fields[name] = (py_type, Field(..., **constraints))
        else:
            fields[name] = (Optional[py_type], Field(default=None, **constraints))

    return create_model("CsvRow", **fields)


def _coerce_bound(col_type: str, value: Any) -> Any:
    if col_type == "date" and isinstance(value, str):
        return date.fromisoformat(value)
    return value
