from __future__ import annotations

import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from app.workers.processors.base import ProcessorResult

VIDEO_TIMEOUT_SECONDS = 300

_ALLOWED_FORMATS = {"mp4", "webm"}
_ALLOWED_RESOLUTIONS = {
    "480p": "854:480",
    "720p": "1280:720",
    "1080p": "1920:1080",
}
_CODECS: dict[str, tuple[str, str, str]] = {
    "mp4": ("libx264", "aac", "video/mp4"),
    "webm": ("libvpx-vp9", "libopus", "video/webm"),
}


def transcode(
    input_stream: BytesIO,
    parameters: dict[str, Any],
) -> ProcessorResult:
    fmt = parameters.get("format", "mp4")
    resolution = parameters.get("resolution")
    crf = parameters.get("crf", 23)
    strip_audio = bool(parameters.get("strip_audio", False))

    if fmt not in _ALLOWED_FORMATS:
        raise ValueError(f"format invalido: '{fmt}' (use mp4 ou webm)")

    if resolution is not None and resolution not in _ALLOWED_RESOLUTIONS:
        raise ValueError(
            f"resolution invalido: '{resolution}' "
            f"(use {sorted(_ALLOWED_RESOLUTIONS)} ou None)"
        )

    if isinstance(crf, bool) or not isinstance(crf, int) or crf < 18 or crf > 28:
        raise ValueError(f"crf invalido: '{crf}' (use inteiro entre 18 e 28)")

    video_codec, audio_codec, content_type = _CODECS[fmt]

    with tempfile.TemporaryDirectory(prefix="video-transcode-") as tmpdir:
        in_path = Path(tmpdir) / "input"
        out_path = Path(tmpdir) / f"output.{fmt}"
        in_path.write_bytes(input_stream.getvalue())

        cmd = [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-c:v", video_codec,
            "-crf", str(crf),
        ]
        if resolution is not None:
            cmd += ["-vf", f"scale={_ALLOWED_RESOLUTIONS[resolution]}"]
        if strip_audio:
            cmd += ["-an"]
        else:
            cmd += ["-c:a", audio_codec]
        cmd += [str(out_path)]

        started = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=VIDEO_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                f"ffmpeg excedeu timeout de {VIDEO_TIMEOUT_SECONDS}s"
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
            "resolution": resolution,
            "crf": crf,
            "strip_audio": strip_audio,
            "output_size_bytes": len(payload),
            "ffmpeg_duration_seconds": round(elapsed, 2),
        },
    )


def _last_stderr_line(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "erro desconhecido"
