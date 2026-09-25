from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib import pdfencrypt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.workers.processors.pdf_merge import merge


def _make_pdf(pages: int = 1, label: str = "x") -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(pages):
        c.drawString(100, 750, f"{label}-{i}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _make_encrypted_pdf() -> bytes:
    buf = BytesIO()
    enc = pdfencrypt.StandardEncryption("owner", "user")
    c = canvas.Canvas(buf, pagesize=letter, encrypt=enc)
    c.drawString(100, 750, "secreto")
    c.showPage()
    c.save()
    return buf.getvalue()


def _make_zip(files: dict[str, bytes]) -> BytesIO:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    buf.seek(0)
    return buf


def test_merge_dois_pdfs_produz_pdf_valido():
    zip_input = _make_zip({"a.pdf": _make_pdf(1), "b.pdf": _make_pdf(1)})

    result = merge(zip_input, {})

    reader = PdfReader(result.output)
    assert len(reader.pages) == 2


def test_total_pages_soma_paginas_de_todos_pdfs():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(2),
        "b.pdf": _make_pdf(3),
        "c.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {})

    assert result.result_metadata["total_pages"] == 6


def test_ordem_alfabetica_default_quando_order_none():
    zip_input = _make_zip({
        "z.pdf": _make_pdf(1),
        "a.pdf": _make_pdf(1),
        "m.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {})

    assert result.result_metadata["files_merged"] == ["a.pdf", "m.pdf", "z.pdf"]


def test_order_customizado_altera_sequencia():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1),
        "b.pdf": _make_pdf(1),
        "c.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {"order": ["c.pdf", "a.pdf", "b.pdf"]})

    assert result.result_metadata["files_merged"] == ["c.pdf", "a.pdf", "b.pdf"]


def test_order_subset_merge_apenas_os_nomes_indicados():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1),
        "b.pdf": _make_pdf(1),
        "c.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {"order": ["b.pdf", "a.pdf"]})

    assert result.result_metadata["files_merged"] == ["b.pdf", "a.pdf"]
    assert result.result_metadata["total_pages"] == 2


def test_page_counts_per_file_reflete_paginas_de_cada_pdf():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(2),
        "b.pdf": _make_pdf(5),
    })

    result = merge(zip_input, {})

    assert result.result_metadata["page_counts_per_file"] == {"a.pdf": 2, "b.pdf": 5}


def test_content_type_e_extensao():
    zip_input = _make_zip({"a.pdf": _make_pdf(1), "b.pdf": _make_pdf(1)})

    result = merge(zip_input, {})

    assert result.output_content_type == "application/pdf"
    assert result.output_extension == "pdf"


def test_pdfs_em_subdiretorios_sao_incluidos():
    zip_input = _make_zip({
        "docs/a.pdf": _make_pdf(1),
        "docs/nested/b.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {})

    assert result.result_metadata["files_merged"] == [
        "docs/a.pdf",
        "docs/nested/b.pdf",
    ]


def test_extensao_case_insensitive():
    zip_input = _make_zip({"A.PDF": _make_pdf(1), "b.Pdf": _make_pdf(1)})

    result = merge(zip_input, {})

    assert len(result.result_metadata["files_merged"]) == 2


def test_arquivos_nao_pdf_no_zip_sao_ignorados():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1),
        "b.pdf": _make_pdf(1),
        "readme.txt": b"nao sou pdf",
        "notas.docx": b"tambem nao",
    })

    result = merge(zip_input, {})

    assert result.result_metadata["files_merged"] == ["a.pdf", "b.pdf"]


def test_zip_invalido_raises():
    with pytest.raises(ValueError, match="ZIP invalido"):
        merge(BytesIO(b"nao sou um zip"), {})


def test_zip_com_um_unico_pdf_raises():
    zip_input = _make_zip({"a.pdf": _make_pdf(1)})

    with pytest.raises(ValueError, match="ao menos 2 PDFs"):
        merge(zip_input, {})


def test_zip_vazio_raises():
    zip_input = _make_zip({})

    with pytest.raises(ValueError, match="ao menos 2 PDFs"):
        merge(zip_input, {})


def test_zip_sem_pdfs_raises():
    zip_input = _make_zip({"readme.txt": b"x", "notas.docx": b"y"})

    with pytest.raises(ValueError, match="ao menos 2 PDFs"):
        merge(zip_input, {})


def test_order_nao_lista_raises():
    zip_input = _make_zip({"a.pdf": _make_pdf(1), "b.pdf": _make_pdf(1)})

    with pytest.raises(ValueError, match="order"):
        merge(zip_input, {"order": "a.pdf,b.pdf"})


def test_order_com_item_nao_string_raises():
    zip_input = _make_zip({"a.pdf": _make_pdf(1), "b.pdf": _make_pdf(1)})

    with pytest.raises(ValueError, match="order"):
        merge(zip_input, {"order": ["a.pdf", 2]})


def test_order_com_nome_inexistente_raises():
    zip_input = _make_zip({"a.pdf": _make_pdf(1), "b.pdf": _make_pdf(1)})

    with pytest.raises(ValueError, match="nao encontrados"):
        merge(zip_input, {"order": ["a.pdf", "fantasma.pdf"]})


def test_pdf_corrompido_no_zip_raises():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1),
        "b.pdf": b"nao sou pdf de verdade",
    })

    with pytest.raises(ValueError, match="invalido"):
        merge(zip_input, {})


def test_pdf_encriptado_no_zip_raises():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1),
        "b.pdf": _make_encrypted_pdf(),
    })

    with pytest.raises(ValueError, match="encriptado"):
        merge(zip_input, {})


def test_output_pdf_reflete_ordem_customizada():
    zip_input = _make_zip({
        "a.pdf": _make_pdf(1, label="AAA"),
        "b.pdf": _make_pdf(1, label="BBB"),
    })

    result = merge(zip_input, {"order": ["b.pdf", "a.pdf"]})
    reader = PdfReader(result.output)

    assert "BBB" in reader.pages[0].extract_text()
    assert "AAA" in reader.pages[1].extract_text()


def test_ordem_alfabetica_default_com_subdirs():
    zip_input = _make_zip({
        "z/1.pdf": _make_pdf(1),
        "a/1.pdf": _make_pdf(1),
    })

    result = merge(zip_input, {})

    assert result.result_metadata["files_merged"] == ["a/1.pdf", "z/1.pdf"]
