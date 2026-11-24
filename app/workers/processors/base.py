from __future__ import annotations

import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, BinaryIO, Protocol

from PIL import Image, ImageOps

MAX_IMAGE_PIXELS = 50_000_000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

FFMPEG_INPUT_OPTIONS = [
    "-protocol_whitelist", "file",
    "-format_whitelist", "mov,matroska,avi,flv,mpegts,mpeg,ogg,asf,mp3,wav,aac,flac",
]


@dataclass
class ProcessorResult:
    output: BytesIO
    output_content_type: str
    output_extension: str
    result_metadata: dict[str, Any] = field(default_factory=dict)


class Processor(Protocol):
    def __call__(
            self,
            input_stream: BytesIO,
            parameters: dict[str, Any],
    ) -> ProcessorResult: ...


def check_pixels(width: int, height: int) -> None:
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            f"imagem de {width}x{height} pixels excede o limite de "
            f"{MAX_IMAGE_PIXELS // 1_000_000} megapixels"
        )


def open_image(stream: BinaryIO) -> Image.Image:
    try:
        image = Image.open(stream)
    except Image.DecompressionBombError as exc:
        raise ValueError(
            f"imagem excede o limite de {MAX_IMAGE_PIXELS // 1_000_000} megapixels"
        ) from exc
    except OSError as exc:
        raise ValueError("imagem invalida ou em formato nao suportado") from exc
    check_pixels(image.width, image.height)
    try:
        image.load()
    except OSError as exc:
        raise ValueError("imagem invalida ou corrompida") from exc
    try:
        ImageOps.exif_transpose(image, in_place=True)
    except Exception:
        # EXIF corrompido: segue com a orientacao gravada nos pixels.
        pass
    return image


def check_zip_size(
        archive: zipfile.ZipFile,
        names: Iterable[str] | None = None,
) -> None:
    infos = archive.infolist() if names is None else [archive.getinfo(n) for n in names]
    total = sum(info.file_size for info in infos)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(
            f"conteudo descompactado ({total // (1024 * 1024)} MB) excede o limite "
            f"de {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB"
        )


def ffmpeg_error_message(stderr: str) -> str:
    if "Format not on whitelist" in stderr:
        return "formato de entrada nao suportado"
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "erro desconhecido"
