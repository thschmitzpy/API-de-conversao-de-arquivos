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


def _encode(image: Image.Image, fmt: str, **kwargs) -> BytesIO:
    buf = BytesIO()
    image.save(buf, format=fmt, **kwargs)
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


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_orientacao_exif_aplicada(fmt):
    exif = Image.Exif()
    exif[0x0112] = 6
    source = _encode(Image.new("RGB", (40, 30)), fmt, exif=exif)

    result = thumbnail(source, {"width": 100, "height": 100})

    out = Image.open(result.output)
    assert out.size == (30, 40)
    assert 0x0112 not in out.getexif()
    assert result.result_metadata["format"] == fmt


def test_exif_corrompido_nao_impede_conversao():
    source = _encode(Image.new("RGB", (40, 30)), "PNG", exif=b"Exif\x00\x00lixo")

    result = thumbnail(source, {"width": 20})

    assert Image.open(result.output).size == (20, 15)


def test_foto_mpo_de_celular_vira_jpeg():
    source = _encode(
        Image.new("RGB", (40, 30), "red"),
        "MPO",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10))],
    )

    result = thumbnail(source, {"width": 20})

    assert result.output_extension == "jpg"
    assert Image.open(result.output).format == "JPEG"


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_transparencia_vira_fundo_branco_em_jpeg(mode):
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0)).convert(mode)
    kwargs = {"transparency": image.getpixel((0, 0))} if mode == "P" else {}

    result = thumbnail(_encode(image, "PNG", **kwargs), {"width": 20, "format": "JPEG"})

    assert Image.open(result.output).convert("RGB").getpixel((10, 10)) == (255, 255, 255)


@pytest.mark.parametrize("fmt", ["PNG", "GIF", "WEBP", "JPEG"])
def test_jpeg_cmyk_vira_rgb(fmt):
    source = _encode(
        Image.new("CMYK", (20, 20), (0, 255, 255, 0)),
        "JPEG",
        icc_profile=b"perfil cmyk",
    )

    result = thumbnail(source, {"width": 20, "format": fmt})

    out = Image.open(result.output)
    red, green, blue = out.convert("RGB").getpixel((10, 10))
    assert out.mode != "CMYK"
    assert red > 240 and green < 15 and blue < 15
    assert "icc_profile" not in out.info


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP", "GIF"])
def test_png_16_bits_mantem_tons_ao_virar_8_bits(fmt):
    source = _encode(Image.new("I;16", (20, 20), 32768), "PNG")

    result = thumbnail(source, {"width": 10, "format": fmt})

    assert abs(Image.open(result.output).convert("L").getpixel((5, 5)) - 127) <= 3


def test_png_16_bits_continua_16_bits_em_png():
    source = _encode(Image.new("I;16", (20, 20), 32768), "PNG")

    result = thumbnail(source, {"width": 10})

    out = Image.open(result.output)
    assert out.mode == "I;16"
    assert out.size == (10, 10)
