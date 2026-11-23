from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

from app.workers.processors.base import ProcessorResult

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

    image = Image.open(input_stream)
    image.load()

    src_format = (image.format or "PNG").upper()
    target_format = requested_format or src_format
    if target_format not in _FORMAT_TO_MIME:
        supported = ", ".join(sorted(_FORMAT_TO_MIME.keys()))
        raise ValueError(
            f"Formato '{target_format}' nao suportado. Suportados: {supported}"
        )

    target_w = width or _UNBOUNDED
    target_h = height or _UNBOUNDED
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    if target_format == "JPEG" and image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")

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


def _dimension(parameters: dict[str, Any], key: str) -> int | None:
    value = parameters.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"'{key}' deve ser inteiro positivo (recebido: {value!r})")
    return value
