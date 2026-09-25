from __future__ import annotations

from io import BytesIO

import pytest
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.workers.processors.pdf_extract_text import extract_text


def _make_pdf(pages_text: list[str]) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for text in pages_text:
        c.drawString(100, 750, text)
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


def _body(result) -> str:
    return result.output.getvalue().decode("utf-8")


def test_extrai_texto_de_pdf_uma_pagina():
    result = extract_text(_make_pdf(["hello world"]), {})

    assert "hello world" in _body(result)


def test_extrai_texto_de_pdf_varias_paginas_junta_com_dupla_quebra():
    result = extract_text(_make_pdf(["primeira", "segunda", "terceira"]), {})
    body = _body(result)

    assert "primeira" in body
    assert "segunda" in body
    assert "terceira" in body
    assert body.count("\n\n") >= 2


def test_output_json_retorna_estrutura_por_pagina():
    import json

    result = extract_text(
        _make_pdf(["um", "dois"]),
        {"output_format": "json"},
    )
    doc = json.loads(_body(result))

    assert doc["total_pages"] == 2
    assert len(doc["pages"]) == 2
    assert doc["pages"][0]["page"] == 1
    assert "um" in doc["pages"][0]["text"]
    assert doc["pages"][1]["page"] == 2
    assert "dois" in doc["pages"][1]["text"]


def test_text_content_type_e_extensao():
    result = extract_text(_make_pdf(["x"]), {})

    assert result.output_content_type == "text/plain; charset=utf-8"
    assert result.output_extension == "txt"


def test_json_content_type_e_extensao():
    result = extract_text(_make_pdf(["x"]), {"output_format": "json"})

    assert result.output_content_type == "application/json"
    assert result.output_extension == "json"


def test_pages_selecionador_de_pagina_unica():
    result = extract_text(
        _make_pdf(["um", "dois", "tres"]),
        {"pages": "2"},
    )
    body = _body(result)

    assert "dois" in body
    assert "um" not in body
    assert "tres" not in body
    assert result.result_metadata["pages_extracted"] == [2]


def test_pages_intervalo():
    result = extract_text(
        _make_pdf(["a", "b", "c", "d"]),
        {"pages": "2-3"},
    )

    assert result.result_metadata["pages_extracted"] == [2, 3]


def test_pages_combinacao_de_intervalo_e_isolada():
    result = extract_text(
        _make_pdf(["a", "b", "c", "d", "e"]),
        {"pages": "1-2,4"},
    )

    assert result.result_metadata["pages_extracted"] == [1, 2, 4]


def test_pages_deduplica_mantendo_ordem():
    result = extract_text(
        _make_pdf(["a", "b", "c"]),
        {"pages": "1,1,2-3,2"},
    )

    assert result.result_metadata["pages_extracted"] == [1, 2, 3]


def test_metadata_reflete_pdf_e_parametros():
    result = extract_text(
        _make_pdf(["a", "b", "c"]),
        {"output_format": "json"},
    )

    meta = result.result_metadata
    assert meta["total_pages"] == 3
    assert meta["pages_extracted"] == [1, 2, 3]
    assert meta["output_format"] == "json"


def test_output_format_invalido_raises():
    with pytest.raises(ValueError, match="output_format"):
        extract_text(_make_pdf(["x"]), {"output_format": "xml"})


def test_pdf_invalido_raises():
    with pytest.raises(ValueError, match="PDF invalido"):
        extract_text(BytesIO(b"nao sou um pdf"), {})


def test_pdf_encriptado_raises():
    with pytest.raises(ValueError, match="encriptado"):
        extract_text(_make_encrypted_pdf(), {})


def test_pages_nao_string_raises():
    with pytest.raises(ValueError, match="pages"):
        extract_text(_make_pdf(["x", "y"]), {"pages": [1, 2]})


def test_pages_vazio_raises():
    with pytest.raises(ValueError, match="vazia"):
        extract_text(_make_pdf(["x"]), {"pages": ""})


def test_pages_intervalo_invertido_raises():
    with pytest.raises(ValueError, match="intervalo"):
        extract_text(_make_pdf(["a", "b", "c"]), {"pages": "3-1"})


def test_pages_zero_raises():
    with pytest.raises(ValueError, match="intervalo|invalida|fora"):
        extract_text(_make_pdf(["a", "b"]), {"pages": "0"})


def test_pages_fora_do_intervalo_raises():
    with pytest.raises(ValueError, match="fora do intervalo"):
        extract_text(_make_pdf(["a", "b"]), {"pages": "5"})


def test_pages_intervalo_nao_numerico_raises():
    with pytest.raises(ValueError, match="intervalo"):
        extract_text(_make_pdf(["a", "b", "c"]), {"pages": "a-b"})


def test_pages_numero_invalido_raises():
    with pytest.raises(ValueError, match="pagina"):
        extract_text(_make_pdf(["a", "b"]), {"pages": "xyz"})
