from __future__ import annotations

from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from app.workers.processors.base import ProcessorResult

_POSITIONS = ("diagonal", "center", "footer", "header")
_COLORS: dict[str, tuple[float, float, float]] = {
    "gray": (0.5, 0.5, 0.5),
    "black": (0.0, 0.0, 0.0),
    "red": (0.8, 0.0, 0.0),
    "blue": (0.0, 0.0, 0.8),
}


def watermark(
        input_stream: BytesIO,
        parameters: dict[str, Any],
) -> ProcessorResult:
    text = parameters.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' obrigatorio e nao pode ser vazio")

    position = parameters.get("position", "diagonal")
    if position not in _POSITIONS:
        raise ValueError(
            f"position invalido: '{position}' (use {', '.join(_POSITIONS)})"
        )

    opacity = parameters.get("opacity", 0.3)
    if (
            isinstance(opacity, bool)
            or not isinstance(opacity, (int, float))
            or not (0 < opacity <= 1)
    ):
        raise ValueError("'opacity' deve ser numero em (0, 1]")

    font_size = parameters.get("font_size", 48)
    if (
            isinstance(font_size, bool)
            or not isinstance(font_size, int)
            or font_size <= 0
    ):
        raise ValueError("'font_size' deve ser inteiro positivo")

    color_name = parameters.get("color", "gray")
    if color_name not in _COLORS:
        raise ValueError(
            f"color invalida: '{color_name}' (use {', '.join(_COLORS)})"
        )
    rgb = _COLORS[color_name]

    try:
        reader = PdfReader(input_stream)
    except PdfReadError as exc:
        raise ValueError(f"PDF invalido: {exc}") from exc

    if reader.is_encrypted:
        raise ValueError("PDF encriptado nao suportado")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("PDF sem paginas")

    writer = PdfWriter()
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay_page = _build_overlay(
            width=width,
            height=height,
            text=text,
            position=position,
            opacity=float(opacity),
            font_size=font_size,
            rgb=rgb,
        )
        page.merge_page(overlay_page)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return ProcessorResult(
        output=output,
        output_content_type="application/pdf",
        output_extension="pdf",
        result_metadata={
            "total_pages": total_pages,
            "pages_watermarked": total_pages,
            "text": text,
            "position": position,
            "opacity": float(opacity),
            "font_size": font_size,
            "color": color_name,
        },
    )


def _build_overlay(
        *,
        width: float,
        height: float,
        text: str,
        position: str,
        opacity: float,
        font_size: int,
        rgb: tuple[float, float, float],
):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    r, g, b = rgb
    c.setFillColor(Color(r, g, b, alpha=opacity))
    c.setFont("Helvetica-Bold", font_size)

    if position == "diagonal":
        c.saveState()
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, text)
        c.restoreState()
    elif position == "center":
        c.drawCentredString(width / 2, height / 2, text)
    elif position == "footer":
        c.drawCentredString(width / 2, max(float(font_size), 30.0), text)
    else:
        c.drawCentredString(width / 2, height - float(font_size), text)

    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]
