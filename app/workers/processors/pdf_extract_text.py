from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.workers.processors.base import ProcessorResult


def extract_text(
    input_stream: BytesIO,
    parameters: dict[str, Any],
) -> ProcessorResult:
    pages_expr = parameters.get("pages")
    output_format = parameters.get("output_format", "text")

    if output_format not in ("text", "json"):
        raise ValueError(
            f"output_format invalido: '{output_format}' (use 'text' ou 'json')"
        )

    try:
        reader = PdfReader(input_stream)
    except PdfReadError as exc:
        raise ValueError(f"PDF invalido: {exc}") from exc

    if reader.is_encrypted:
        raise ValueError("PDF encriptado nao suportado")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("PDF sem paginas")

    if pages_expr is None:
        page_numbers = list(range(1, total_pages + 1))
    else:
        if not isinstance(pages_expr, str):
            raise ValueError("'pages' deve ser string (ex: '1-3,5,7-9')")
        page_numbers = _parse_pages(pages_expr, total_pages)

    extracted: list[tuple[int, str]] = []
    for num in page_numbers:
        page = reader.pages[num - 1]
        extracted.append((num, page.extract_text() or ""))

    metadata = {
        "total_pages": total_pages,
        "pages_extracted": page_numbers,
        "output_format": output_format,
    }

    if output_format == "text":
        body = "\n\n".join(text for _, text in extracted)
        payload = body.encode("utf-8")
        return ProcessorResult(
            output=BytesIO(payload),
            output_content_type="text/plain; charset=utf-8",
            output_extension="txt",
            result_metadata=metadata,
        )

    doc = {
        "total_pages": total_pages,
        "pages": [{"page": num, "text": text} for num, text in extracted],
    }
    payload = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    return ProcessorResult(
        output=BytesIO(payload),
        output_content_type="application/json",
        output_extension="json",
        result_metadata=metadata,
    )


def _parse_pages(expr: str, total_pages: int) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()

    parts = [p.strip() for p in expr.split(",") if p.strip()]
    if not parts:
        raise ValueError("expressao 'pages' vazia")

    for part in parts:
        if "-" in part:
            a_str, _, b_str = part.partition("-")
            try:
                a, b = int(a_str), int(b_str)
            except ValueError as exc:
                raise ValueError(
                    f"intervalo invalido em 'pages': '{part}'"
                ) from exc
            if a < 1 or b < 1 or a > b:
                raise ValueError(
                    f"intervalo invalido em 'pages': '{part}' (use A-B com 1<=A<=B)"
                )
            if b > total_pages:
                raise ValueError(
                    f"pagina {b} fora do intervalo (PDF tem {total_pages})"
                )
            for n in range(a, b + 1):
                if n not in seen:
                    seen.add(n)
                    result.append(n)
        else:
            try:
                n = int(part)
            except ValueError as exc:
                raise ValueError(f"pagina invalida em 'pages': '{part}'") from exc
            if n < 1 or n > total_pages:
                raise ValueError(
                    f"pagina {n} fora do intervalo (PDF tem {total_pages})"
                )
            if n not in seen:
                seen.add(n)
                result.append(n)

    return result
