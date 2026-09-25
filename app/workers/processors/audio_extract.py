from __future__ import annotations

import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from app.workers.processors.base import ProcessorResult

AUDIO_TIMEOUT_SECONDS = 180

_FORMATS: dict[str, tuple[str, str]] = {
    "mp3": ("libmp3lame", "audio/mpeg"),
    "wav": ("pcm_s16le", "audio/wav"),
    "ogg": ("libvorbis", "audio/ogg"),
    "aac": ("aac", "audio/aac"),
}
_ALLOWED_BITRATES = {"128k", "192k", "256k", "320k"}
_ALLOWED_SAMPLE_RATES = {22050, 44100, 48000}
_ALLOWED_CHANNELS = {1, 2}


def extract(
        input_stream: BytesIO,
        parameters: dict[str, Any],
) -> ProcessorResult:
    fmt = parameters.get("format", "mp3")
    bitrate = parameters.get("bitrate", "192k" if fmt != "wav" else None)
    sample_rate = parameters.get("sample_rate")
    channels = parameters.get("channels")

    if fmt not in _FORMATS:
        raise ValueError(
            f"format invalido: '{fmt}' (use {sorted(_FORMATS)})"
        )

    if fmt == "wav":
        if bitrate is not None:
            raise ValueError("wav e PCM: 'bitrate' deve ser omitido")
    else:
        if bitrate is not None and bitrate not in _ALLOWED_BITRATES:
            raise ValueError(
                f"bitrate invalido: '{bitrate}' "
                f"(use {sorted(_ALLOWED_BITRATES)} ou None)"
            )

    if sample_rate is not None:
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
            raise ValueError(f"sample_rate invalido: '{sample_rate}'")
        if sample_rate not in _ALLOWED_SAMPLE_RATES:
            raise ValueError(
                f"sample_rate invalido: '{sample_rate}' "
                f"(use {sorted(_ALLOWED_SAMPLE_RATES)} ou None)"
            )

    if channels is not None:
        if isinstance(channels, bool) or not isinstance(channels, int):
            raise ValueError(f"channels invalido: '{channels}'")
        if channels not in _ALLOWED_CHANNELS:
            raise ValueError(
                f"channels invalido: '{channels}' "
                f"(use {sorted(_ALLOWED_CHANNELS)} ou None)"
            )

    codec, content_type = _FORMATS[fmt]

    with tempfile.TemporaryDirectory(prefix="audio-extract-") as tmpdir:
        in_path = Path(tmpdir) / "input"
        out_path = Path(tmpdir) / f"output.{fmt}"
        in_path.write_bytes(input_stream.getvalue())

        cmd = [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-vn",
            "-c:a", codec,
        ]
        if bitrate is not None:
            cmd += ["-b:a", bitrate]
        if sample_rate is not None:
            cmd += ["-ar", str(sample_rate)]
        if channels is not None:
            cmd += ["-ac", str(channels)]
        cmd += [str(out_path)]

        started = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=AUDIO_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                f"ffmpeg excedeu timeout de {AUDIO_TIMEOUT_SECONDS}s"
            ) from exc
        elapsed = time.monotonic() - started

        if result.returncode != 0:
            raise ValueError(f"ffmpeg falhou: {_last_stderr_line(result.stderr)}")

        payload = out_path.read_bytes()

    return ProcessorResult(
        output=BytesIO(payload),
        output_content_type=content_type,
        output_extension=fmt,
        result_metadata={
            "format": fmt,
            "bitrate": bitrate,
            "sample_rate": sample_rate,
            "channels": channels,
            "output_size_bytes": len(payload),
            "ffmpeg_duration_seconds": round(elapsed, 2),
        },
    )


def _last_stderr_line(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "erro desconhecido"
