from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.workers.processors.base import ProcessorResult


def merge(
    input_stream: BytesIO,
    parameters: dict[str, Any],
) -> ProcessorResult:
    order = parameters.get("order")

    try:
        archive = zipfile.ZipFile(input_stream)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Arquivo ZIP invalido: {exc}") from exc

    pdf_names = sorted(
        n for n in archive.namelist()
        if n.lower().endswith(".pdf") and not n.endswith("/")
    )
    if len(pdf_names) < 2:
        raise ValueError(
            f"ZIP deve conter ao menos 2 PDFs (encontrados: {len(pdf_names)})"
        )

    if order is not None:
        if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
            raise ValueError("'order' deve ser lista de strings")
        missing = [n for n in order if n not in pdf_names]
        if missing:
            raise ValueError(f"nomes em 'order' nao encontrados no ZIP: {missing}")
        pdf_names = order

    writer = PdfWriter()
    page_counts: dict[str, int] = {}
    total_pages = 0

    for name in pdf_names:
        with archive.open(name) as fp:
            data = fp.read()
        try:
            reader = PdfReader(BytesIO(data))
        except PdfReadError as exc:
            raise ValueError(f"PDF '{name}' invalido: {exc}") from exc
        if reader.is_encrypted:
            raise ValueError(f"PDF '{name}' encriptado nao suportado")
        n_pages = len(reader.pages)
        if n_pages == 0:
            raise ValueError(f"PDF '{name}' sem paginas")
        for page in reader.pages:
            writer.add_page(page)
        page_counts[name] = n_pages
        total_pages += n_pages

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return ProcessorResult(
        output=output,
        output_content_type="application/pdf",
        output_extension="pdf",
        result_metadata={
            "files_merged": pdf_names,
            "total_pages": total_pages,
            "page_counts_per_file": page_counts,
        },
    )
