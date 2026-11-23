import pytest
from fastapi import HTTPException

from app.api.jobs import _safe_content_type, _safe_filename


def test_safe_filename_remove_diretorios():
    assert _safe_filename("C:\\Users\\fulano\\foto.png") == "foto.png"
    assert _safe_filename("../../etc/foto.png") == "foto.png"


def test_safe_filename_remove_caracteres_de_controle():
    assert _safe_filename("fo\x00to\r\n.png") == "foto.png"


def test_safe_filename_aceita_ate_255_bytes():
    nome = "a" * 251 + ".png"
    assert _safe_filename(nome) == nome


@pytest.mark.parametrize("nome", ["a" * 252 + ".png", "é" * 128 + ".png"])
def test_safe_filename_acima_de_255_bytes_raises(nome):
    with pytest.raises(HTTPException) as exc:
        _safe_filename(nome)
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "raw",
    [None, "", "image/" + "x" * 200, "image/png\r\nX-Evil: 1"],
)
def test_safe_content_type_invalido_vira_octet_stream(raw):
    assert _safe_content_type(raw) == "application/octet-stream"


def test_safe_content_type_valido_passa():
    assert _safe_content_type("image/png") == "image/png"
