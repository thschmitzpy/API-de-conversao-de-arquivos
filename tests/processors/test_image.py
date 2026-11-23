from __future__ import annotations

import random
from io import BytesIO

import pytest
from PIL import Image

from app.workers.processors import base
from app.workers.processors.image import thumbnail


def _make_png(width: int, height: int, mode: str = "RGB") -> BytesIO:
    if mode == "RGBA":
        img = Image.new("RGBA", (width, height), color=(255, 0, 0, 128))
    else:
        img = Image.new(mode, (width, height), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _make_noisy_png(size: int, seed: int = 42) -> BytesIO:
    rng = random.Random(seed)
    pixels = [
        (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        for _ in range(size * size)
    ]
    img = Image.new("RGB", (size, size))
    img.putdata(pixels)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_reduz_dimensoes_mantendo_aspect_ratio():
    result = thumbnail(_make_png(200, 100), {"width": 100})

    out = Image.open(result.output)
    assert out.width == 100
    assert out.height == 50


def test_mantem_formato_original_quando_nao_especificado():
    result = thumbnail(_make_png(200, 100), {"width": 100})

    assert result.output_content_type == "image/png"
    assert result.output_extension == "png"


def test_converte_para_formato_especificado():
    result = thumbnail(_make_png(200, 100), {"width": 100, "format": "JPEG"})

    assert result.output_content_type == "image/jpeg"
    assert result.output_extension == "jpg"
    assert Image.open(result.output).format == "JPEG"


def test_rgba_convertido_para_rgb_ao_salvar_jpeg():
    result = thumbnail(
        _make_png(100, 100, mode="RGBA"),
        {"width": 50, "format": "JPEG"},
    )

    assert Image.open(result.output).mode == "RGB"


def test_apenas_width_calcula_height_por_ratio():
    result = thumbnail(_make_png(400, 200), {"width": 100})

    out = Image.open(result.output)
    assert out.width == 100
    assert out.height == 50


def test_apenas_height_calcula_width_por_ratio():
    result = thumbnail(_make_png(400, 200), {"height": 50})

    out = Image.open(result.output)
    assert out.width == 100
    assert out.height == 50


def test_sem_width_nem_height_raises():
    with pytest.raises(ValueError, match="width"):
        thumbnail(_make_png(100, 100), {})


def test_format_invalido_raises():
    with pytest.raises(ValueError, match="BMP"):
        thumbnail(_make_png(100, 100), {"width": 50, "format": "BMP"})


def test_format_case_insensitive():
    result = thumbnail(_make_png(200, 100), {"width": 100, "format": "jpeg"})

    assert result.output_content_type == "image/jpeg"
    assert result.output_extension == "jpg"


def test_metadata_reflete_dimensoes_e_formato_alvo():
    result = thumbnail(_make_png(200, 100), {"width": 100, "format": "PNG"})

    assert result.result_metadata["width"] == 100
    assert result.result_metadata["height"] == 50
    assert result.result_metadata["format"] == "PNG"
    assert result.result_metadata["size_bytes"] > 0


def test_quality_menor_gera_arquivo_menor_em_jpeg():
    high = thumbnail(
        _make_noisy_png(500),
        {"width": 400, "format": "JPEG", "quality": 95},
    )
    low = thumbnail(
        _make_noisy_png(500),
        {"width": 400, "format": "JPEG", "quality": 10},
    )

    assert low.result_metadata["size_bytes"] < high.result_metadata["size_bytes"]


def test_thumbnail_nao_aumenta_imagem():
    result = thumbnail(_make_png(50, 50), {"width": 200, "height": 200})

    out = Image.open(result.output)
    assert out.width == 50
    assert out.height == 50


@pytest.mark.parametrize(
    "params",
    [
        {"width": True},
        {"width": 0},
        {"height": -10},
        {"width": "100"},
        {"width": 10.5},
    ],
)
def test_dimensao_invalida_raises(params):
    with pytest.raises(ValueError, match="inteiro positivo"):
        thumbnail(_make_png(100, 100), params)


@pytest.mark.parametrize("quality", [True, 0, 101, "85"])
def test_quality_invalida_raises(quality):
    with pytest.raises(ValueError, match="quality"):
        thumbnail(
            _make_png(100, 100),
            {"width": 50, "format": "JPEG", "quality": quality},
        )


def test_imagem_acima_do_limite_de_pixels_raises(monkeypatch):
    monkeypatch.setattr(base, "MAX_IMAGE_PIXELS", 100 * 100 - 1)
    with pytest.raises(ValueError, match="megapixels"):
        thumbnail(_make_png(100, 100), {"width": 50})


def test_arquivo_que_nao_e_imagem_raises():
    with pytest.raises(ValueError, match="imagem invalida"):
        thumbnail(BytesIO(b"nao sou uma imagem"), {"width": 50})
