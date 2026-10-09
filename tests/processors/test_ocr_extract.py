from __future__ import annotations

import json
import shutil
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from app.workers.processors.ocr_extract import extract

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract nao instalado",
)


def _default_font(size: int = 48):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _make_png(text: str, size: tuple[int, int] = (600, 150)) -> BytesIO:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), text, fill="black", font=_default_font())
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _make_webp(text: str) -> BytesIO:
    img = Image.new("RGB", (600, 150), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), text, fill="black", font=_default_font())
    buf = BytesIO()
    img.save(buf, format="WEBP")
    buf.seek(0)
    return buf


def _make_pdf(texts: list[str]) -> BytesIO:
    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 36)
    for text in texts:
        c.drawString(100, 500, text)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf


def test_ocr_imagem_png_extrai_texto():  # happy paths
    result = extract(_make_png("HELLO WORLD"), {})

    body = result.output.read().decode("utf-8").upper()
    assert "HELLO" in body
    assert "WORLD" in body


def test_ocr_imagem_webp_extrai_texto():
    result = extract(_make_webp("TESTE WEBP"), {})

    body = result.output.read().decode("utf-8").upper()
    assert "TESTE" in body


def test_ocr_pdf_processa_todas_paginas():
    result = extract(_make_pdf(["PAGINA UM", "PAGINA DOIS"]), {})

    assert result.result_metadata["pages_processed"] == 2
    body = result.output.read().decode("utf-8").upper()
    assert "PAGINA" in body


def test_output_format_json_estrutura():
    result = extract(_make_pdf(["ABC", "DEF"]), {"output_format": "json"})

    doc = json.loads(result.output.read().decode("utf-8"))
    assert doc["source_type"] == "pdf"
    assert len(doc["pages"]) == 2
    assert doc["pages"][0]["page"] == 1
    assert doc["pages"][1]["page"] == 2


def test_content_type_text():
    result = extract(_make_png("X"), {})

    assert result.output_content_type == "text/plain; charset=utf-8"
    assert result.output_extension == "txt"


def test_content_type_json():
    result = extract(_make_png("X"), {"output_format": "json"})

    assert result.output_content_type == "application/json"
    assert result.output_extension == "json"


def test_metadata_imagem_sem_dpi():  # metadata
    result = extract(_make_png("X"), {})

    meta = result.result_metadata
    assert meta["source_type"] == "image"
    assert meta["pages_processed"] == 1
    assert "dpi" not in meta


def test_metadata_pdf_inclui_dpi():
    result = extract(_make_pdf(["X"]), {"dpi": 150})

    meta = result.result_metadata
    assert meta["source_type"] == "pdf"
    assert meta["dpi"] == 150


def test_lang_persistido_no_metadata():
    result = extract(_make_png("X"), {"lang": "eng"})

    assert result.result_metadata["lang"] == "eng"


def test_lang_vazio_raises():  # validação de parâmetros
    with pytest.raises(ValueError, match="'lang'"):
        extract(_make_png("X"), {"lang": "   "})


def test_lang_nao_string_raises():
    with pytest.raises(ValueError, match="'lang'"):
        extract(_make_png("X"), {"lang": 123})


def test_lang_nao_instalado_raises():
    with pytest.raises(ValueError, match="nao instalado"):
        extract(_make_png("X"), {"lang": "jpn"})


def test_output_format_invalido_raises():
    with pytest.raises(ValueError, match="output_format"):
        extract(_make_png("X"), {"output_format": "yaml"})


def test_dpi_abaixo_do_minimo_raises():
    with pytest.raises(ValueError, match="dpi"):
        extract(_make_pdf(["X"]), {"dpi": 50})


def test_dpi_acima_do_maximo_raises():
    with pytest.raises(ValueError, match="dpi"):
        extract(_make_pdf(["X"]), {"dpi": 1200})


def test_dpi_bool_raises():
    with pytest.raises(ValueError, match="dpi"):
        extract(_make_pdf(["X"]), {"dpi": True})


def test_dpi_float_raises():
    with pytest.raises(ValueError, match="dpi"):
        extract(_make_pdf(["X"]), {"dpi": 200.0})


def test_entrada_nao_suportada_raises():  # detecção de tipo e entradas inválidas
    with pytest.raises(ValueError, match="nao e PDF nem imagem"):
        extract(BytesIO(b"nao sou nada reconhecivel"), {})


def test_pdf_invalido_raises():
    with pytest.raises(ValueError, match="PDF invalido"):
        extract(BytesIO(b"%PDF-fake content aqui"), {})


def test_imagem_invalida_raises():
    bad_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    with pytest.raises(ValueError, match="imagem invalida"):
        extract(BytesIO(bad_png), {})
