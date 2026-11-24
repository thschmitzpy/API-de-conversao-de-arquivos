from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

from app.workers.processors.base import ProcessorResult, open_image

_FORMAT_TO_EXT: dict[str, str] = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}
_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
# Modos que cada formato grava sem conversao previa.
_SAVE_MODES: dict[str, set[str]] = {
    "JPEG": {"1", "L", "RGB"},
    "PNG": {"1", "L", "LA", "P", "I", "I;16", "RGB", "RGBA"},
    "WEBP": {"1", "L", "LA", "P", "RGB", "RGBA"},
    "GIF": {"1", "L", "LA", "P", "RGB", "RGBA"},
}
_DEFAULT_QUALITY = 85
_UNBOUNDED = 100_000


def thumbnail(
    input_stream: BytesIO,
    parameters: dict[str, Any],
) -> ProcessorResult:
    width = _dimension(parameters, "width")
    height = _dimension(parameters, "height")
    if width is None and height is None:
        raise ValueError("parameters deve conter 'width' e/ou 'height'")

    quality = parameters.get("quality", _DEFAULT_QUALITY)
    if (
            isinstance(quality, bool)
            or not isinstance(quality, int)
            or not 1 <= quality <= 100
    ):
        raise ValueError(
            f"'quality' deve ser inteiro entre 1 e 100 (recebido: {quality!r})"
        )

    requested_format = str(parameters.get("format", "")).upper() or None

    image = open_image(input_stream)

    src_format = (image.format or "PNG").upper()
    if src_format == "MPO":
        # JPEG de celular com imagens extras embutidas (HDR, profundidade).
        src_format = "JPEG"
    target_format = requested_format or src_format
    if target_format not in _FORMAT_TO_MIME:
        supported = ", ".join(sorted(_FORMAT_TO_MIME.keys()))
        raise ValueError(
            f"Formato '{target_format}' nao suportado. Suportados: {supported}"
        )

    target_w = width or _UNBOUNDED
    target_h = height or _UNBOUNDED
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    image = _to_save_mode(image, target_format)

    save_kwargs: dict[str, Any] = {}
    if target_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality
    if target_format in ("JPEG", "PNG"):
        save_kwargs["optimize"] = True

    output = BytesIO()
    image.save(output, format=target_format, **save_kwargs)
    output.seek(0)

    return ProcessorResult(
        output=output,
        output_content_type=_FORMAT_TO_MIME[target_format],
        output_extension=_FORMAT_TO_EXT[target_format],
        result_metadata={
            "width": image.width,
            "height": image.height,
            "format": target_format,
            "size_bytes": output.getbuffer().nbytes,
        },
    )


def _to_save_mode(image: Image.Image, target_format: str) -> Image.Image:
    if target_format == "JPEG" and image.has_transparency_data:
        return _flatten_on_white(image)
    if image.mode in _SAVE_MODES[target_format]:
        return image
    if image.mode.startswith("I;16"):

        return image.convert("I").point(lambda value: value * (1 / 257)).convert("L")
    converted = image.convert("RGB")

    converted.info.pop("icc_profile", None)
    return converted


def _flatten_on_white(image: Image.Image) -> Image.Image:
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _dimension(parameters: dict[str, Any], key: str) -> int | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"'{key}' deve ser inteiro positivo (recebido: {value!r})")
    return value
