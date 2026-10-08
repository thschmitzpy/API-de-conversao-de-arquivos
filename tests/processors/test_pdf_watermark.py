from __future__ import annotations

from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.workers.processors.pdf_watermark import watermark


def _make_pdf(pages: int = 1, label: str = "x") -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(pages):
        c.drawString(100, 750, f"{label}-{i}")
        c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _make_encrypted_pdf() -> BytesIO:
    buf = BytesIO()
    enc = pdfencrypt.StandardEncryption("owner", "user")
    c = canvas.Canvas(buf, pagesize=letter, encrypt=enc)
    c.drawString(100, 750, "secreto")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def test_watermark_diagonal_preserva_numero_de_paginas():
    result = watermark(_make_pdf(3), {"text": "DRAFT"})

    reader = PdfReader(result.output)
    assert len(reader.pages) == 3


@pytest.mark.parametrize("position", ["diagonal", "center", "footer", "header"])
def test_watermark_todas_as_posicoes_renderizam(position):
    result = watermark(_make_pdf(1), {"text": "X", "position": position})

    reader = PdfReader(result.output)
    assert len(reader.pages) == 1
    assert result.result_metadata["position"] == position


def test_todas_as_paginas_sao_marcadas():
    result = watermark(_make_pdf(5), {"text": "DRAFT"})

    assert result.result_metadata["pages_watermarked"] == 5
    assert result.result_metadata["total_pages"] == 5


def test_content_type_e_extensao():
    result = watermark(_make_pdf(1), {"text": "X"})

    assert result.output_content_type == "application/pdf"
    assert result.output_extension == "pdf"


def test_defaults_aplicados_quando_omitidos():
    result = watermark(_make_pdf(1), {"text": "DRAFT"})

    meta = result.result_metadata
    assert meta["position"] == "diagonal"
    assert meta["opacity"] == 0.3
    assert meta["font_size"] == 48
    assert meta["color"] == "gray"


def test_metadata_preenche_campos_customizados():
    result = watermark(
        _make_pdf(1),
        {
            "text": "CONFIDENCIAL",
            "position": "footer",
            "opacity": 0.7,
            "font_size": 24,
            "color": "red",
        },
    )

    meta = result.result_metadata
    assert meta["text"] == "CONFIDENCIAL"
    assert meta["position"] == "footer"
    assert meta["opacity"] == 0.7
    assert meta["font_size"] == 24
    assert meta["color"] == "red"



def test_text_ausente_raises():                                    # -- validação de 'text'

    with pytest.raises(ValueError, match="'text' obrigatorio"):
        watermark(_make_pdf(1), {})


def test_text_vazio_raises():
    with pytest.raises(ValueError, match="'text' obrigatorio"):
        watermark(_make_pdf(1), {"text": "   "})


def test_text_nao_string_raises():
    with pytest.raises(ValueError, match="'text' obrigatorio"):
        watermark(_make_pdf(1), {"text": 123})



def test_position_invalido_raises():                                 # -- validação de 'position'
    with pytest.raises(ValueError, match="position invalido"):
        watermark(_make_pdf(1), {"text": "X", "position": "topo"})



def test_opacity_zero_raises():                                      # -- validação de 'opacity'
    with pytest.raises(ValueError, match="opacity"):
        watermark(_make_pdf(1), {"text": "X", "opacity": 0})


def test_opacity_acima_de_um_raises():
    with pytest.raises(ValueError, match="opacity"):
        watermark(_make_pdf(1), {"text": "X", "opacity": 1.5})


def test_opacity_negativo_raises():
    with pytest.raises(ValueError, match="opacity"):
        watermark(_make_pdf(1), {"text": "X", "opacity": -0.1})


def test_opacity_bool_raises():
    with pytest.raises(ValueError, match="opacity"):
        watermark(_make_pdf(1), {"text": "X", "opacity": True})


def test_opacity_nao_numero_raises():
    with pytest.raises(ValueError, match="opacity"):
        watermark(_make_pdf(1), {"text": "X", "opacity": "meio"})


def test_font_size_zero_raises():                                             # -- validação de 'font_size'
    with pytest.raises(ValueError, match="font_size"):
        watermark(_make_pdf(1), {"text": "X", "font_size": 0})


def test_font_size_negativo_raises():
    with pytest.raises(ValueError, match="font_size"):
        watermark(_make_pdf(1), {"text": "X", "font_size": -5})


def test_font_size_float_raises():
    with pytest.raises(ValueError, match="font_size"):
        watermark(_make_pdf(1), {"text": "X", "font_size": 12.5})


def test_font_size_bool_raises():
    with pytest.raises(ValueError, match="font_size"):
        watermark(_make_pdf(1), {"text": "X", "font_size": True})



def test_color_invalido_raises():                                            # -- validação de 'color'
    with pytest.raises(ValueError, match="color invalida"):
        watermark(_make_pdf(1), {"text": "X", "color": "verde"})


@pytest.mark.parametrize("color", ["gray", "black", "red", "blue"])
def test_todas_as_cores_aceitas(color):
    result = watermark(_make_pdf(1), {"text": "X", "color": color})

    assert result.result_metadata["color"] == color


def test_pdf_invalido_raises():                                              # -- PDF de entrada inválido
    with pytest.raises(ValueError, match="PDF invalido"):
        watermark(BytesIO(b"nao sou pdf"), {"text": "X"})


def test_pdf_encriptado_raises():
    with pytest.raises(ValueError, match="encriptado"):
        watermark(_make_encrypted_pdf(), {"text": "X"})
