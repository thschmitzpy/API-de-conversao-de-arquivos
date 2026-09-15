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
    width = parameters.get("width")
    height = parameters.get("height")
    if not width and not height:
        raise ValueError("parameters deve conter 'width' e/ou 'height'")

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

    target_w = int(width) if width else _UNBOUNDED
    target_h = int(height) if height else _UNBOUNDED
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    if target_format == "JPEG" and image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")

    save_kwargs: dict[str, Any] = {}
    if target_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = int(parameters.get("quality", _DEFAULT_QUALITY))
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
