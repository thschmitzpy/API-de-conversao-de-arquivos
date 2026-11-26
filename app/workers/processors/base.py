from __future__ import annotations

import subprocess
import tempfile
import threading
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from PIL import Image, ImageOps

from app.workers.progress import report_progress

MAX_IMAGE_PIXELS = 50_000_000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

FFMPEG_INPUT_OPTIONS = [
    "-protocol_whitelist", "file",
    "-format_whitelist", "mov,matroska,avi,flv,mpegts,mpeg,ogg,asf,mp3,wav,aac,flac",
]

FFPROBE_TIMEOUT_SECONDS = 30


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


def run_ffmpeg(input_path: Path, output_args: list[str], timeout: int) -> None:
    duration = _probe_duration(input_path)
    cmd = [
        "ffmpeg", "-y",
        "-nostats", "-progress", "pipe:1",
        *FFMPEG_INPUT_OPTIONS,
        "-i", str(input_path),
        *output_args,
    ]

    with tempfile.TemporaryFile(mode="w+") as stderr:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True)
        expired = threading.Event()

        def expire() -> None:
            expired.set()
            process.kill()

        timer = threading.Timer(timeout, expire)
        timer.start()
        try:
            for line in process.stdout:
                key, _, value = line.strip().partition("=")
                if duration and key == "out_time_us" and value.isdigit():
                    report_progress(int(value) / 1_000_000 / duration)
            returncode = process.wait()
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()

        if expired.is_set():
            raise ValueError(f"ffmpeg excedeu timeout de {timeout}s")
        if returncode != 0:
            stderr.seek(0)
            raise ValueError(f"ffmpeg falhou: {ffmpeg_error_message(stderr.read())}")


def _probe_duration(path: Path) -> float | None:
    cmd = [
        "ffprobe", "-v", "error",
        *FFMPEG_INPUT_OPTIONS,
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT_SECONDS, check=False
        )
        duration = float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return None
    return duration if duration > 0 else None
