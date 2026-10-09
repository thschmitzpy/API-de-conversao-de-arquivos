from __future__ import annotations

import json
from functools import lru_cache
from io import BytesIO
from typing import Any

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, UnidentifiedImageError

from app.workers.processors.base import ProcessorResult

_PDF_MAGIC = b"%PDF-"
_IMAGE_MAGICS = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)


@lru_cache(maxsize=1)
def _available_langs() -> frozenset[str]:
    return frozenset(pytesseract.get_languages(config=""))


def _detect_type(data: bytes) -> str:
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    for magic in _IMAGE_MAGICS:
        if data.startswith(magic):
            return "image"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image"
    raise ValueError(
        "entrada nao e PDF nem imagem suportada (PNG/JPEG/GIF/WEBP)"
    )


def extract(
        input_stream: BytesIO,
        parameters: dict[str, Any],
) -> ProcessorResult:
    lang = parameters.get("lang", "eng")
    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("'lang' deve ser string nao vazia (ex: 'eng', 'por+eng')")

    output_format = parameters.get("output_format", "text")
    if output_format not in ("text", "json"):
        raise ValueError(
            f"output_format invalido: '{output_format}' (use 'text' ou 'json')"
        )

    dpi = parameters.get("dpi", 200)
    if (
            isinstance(dpi, bool)
            or not isinstance(dpi, int)
            or not (72 <= dpi <= 600)
    ):
        raise ValueError("'dpi' deve ser inteiro entre 72 e 600")

    requested = [p.strip() for p in lang.split("+") if p.strip()]
    missing = [p for p in requested if p not in _available_langs()]
    if missing:
        raise ValueError(
            f"idioma(s) nao instalado(s) no tesseract: {missing} "
            f"(disponiveis: {sorted(_available_langs())})"
        )

    data = input_stream.read()
    source_type = _detect_type(data)

    pages_text: list[tuple[int, str]] = []

    if source_type == "image":
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"imagem invalida: {exc}") from exc
        text = pytesseract.image_to_string(image, lang=lang)
        pages_text.append((1, text))
    else:
        try:
            pdf = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as exc:
            raise ValueError(f"PDF invalido: {exc}") from exc

        n_pages = len(pdf)
        if n_pages == 0:
            raise ValueError("PDF sem paginas")

        scale = dpi / 72.0
        for i in range(n_pages):
            page = pdf[i]
            pil_image = page.render(scale=scale).to_pil()
            text = pytesseract.image_to_string(pil_image, lang=lang)
            pages_text.append((i + 1, text))

    metadata: dict[str, Any] = {
        "source_type": source_type,
        "pages_processed": len(pages_text),
        "lang": lang,
        "output_format": output_format,
    }
    if source_type == "pdf":
        metadata["dpi"] = dpi

    if output_format == "text":
        body = "\n\n".join(text for _, text in pages_text)
        payload = body.encode("utf-8")
        return ProcessorResult(
            output=BytesIO(payload),
            output_content_type="text/plain; charset=utf-8",
            output_extension="txt",
            result_metadata=metadata,
        )

    doc = {
        "source_type": source_type,
        "pages": [{"page": p, "text": t} for p, t in pages_text],
    }
    payload = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    return ProcessorResult(
        output=BytesIO(payload),
        output_content_type="application/json",
        output_extension="json",
        result_metadata=metadata,
    )
