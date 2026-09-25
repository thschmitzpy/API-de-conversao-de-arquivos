from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from app.workers.processors.video_transcode import transcode

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="requer ffmpeg no PATH",
)


@pytest.fixture(scope="module")
def sample_mp4() -> bytes:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "s.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(out),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return out.read_bytes()


def _probe_video_dims(data: bytes) -> tuple[int, int]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "probe"
        p.write_bytes(data)
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0:s=x",
                str(p),
            ],
            capture_output=True, text=True, check=True,
        )
        w, h = r.stdout.strip().split("x")
        return int(w), int(h)


def _has_audio(data: bytes) -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "probe"
        p.write_bytes(data)
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(p),
            ],
            capture_output=True, text=True, check=True,
        )
        return "audio" in r.stdout


def test_transcode_mp4_default(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {})

    assert result.output_extension == "mp4"
    assert result.output_content_type == "video/mp4"
    w, h = _probe_video_dims(result.output.getvalue())
    assert w > 0 and h > 0


def test_transcode_webm(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {"format": "webm"})

    assert result.output_extension == "webm"
    assert result.output_content_type == "video/webm"


def test_resolution_480p_aplicada(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {"resolution": "480p"})

    assert _probe_video_dims(result.output.getvalue()) == (854, 480)


def test_resolution_720p_aplicada(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {"resolution": "720p"})

    assert _probe_video_dims(result.output.getvalue()) == (1280, 720)


def test_strip_audio_remove_faixa(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {"strip_audio": True})

    assert not _has_audio(result.output.getvalue())


def test_sem_strip_audio_mantem_faixa(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {})

    assert _has_audio(result.output.getvalue())


def test_crf_maior_gera_arquivo_menor(sample_mp4):
    baixo = transcode(BytesIO(sample_mp4), {"crf": 18})
    alto = transcode(BytesIO(sample_mp4), {"crf": 28})

    assert (
            alto.result_metadata["output_size_bytes"]
            < baixo.result_metadata["output_size_bytes"]
    )


def test_metadata_reflete_parametros(sample_mp4):
    result = transcode(
        BytesIO(sample_mp4),
        {"format": "webm", "resolution": "480p", "crf": 25, "strip_audio": True},
    )

    meta = result.result_metadata
    assert meta["format"] == "webm"
    assert meta["resolution"] == "480p"
    assert meta["crf"] == 25
    assert meta["strip_audio"] is True
    assert meta["output_size_bytes"] > 0
    assert meta["ffmpeg_duration_seconds"] >= 0


def test_format_invalido_raises(sample_mp4):
    with pytest.raises(ValueError, match="format"):
        transcode(BytesIO(sample_mp4), {"format": "avi"})


def test_resolution_invalida_raises(sample_mp4):
    with pytest.raises(ValueError, match="resolution"):
        transcode(BytesIO(sample_mp4), {"resolution": "4k"})


def test_crf_abaixo_do_minimo_raises(sample_mp4):
    with pytest.raises(ValueError, match="crf"):
        transcode(BytesIO(sample_mp4), {"crf": 17})


def test_crf_acima_do_maximo_raises(sample_mp4):
    with pytest.raises(ValueError, match="crf"):
        transcode(BytesIO(sample_mp4), {"crf": 29})


def test_crf_nao_int_raises(sample_mp4):
    with pytest.raises(ValueError, match="crf"):
        transcode(BytesIO(sample_mp4), {"crf": 23.5})


def test_crf_bool_raises(sample_mp4):
    with pytest.raises(ValueError, match="crf"):
        transcode(BytesIO(sample_mp4), {"crf": True})


def test_input_nao_video_raises():
    with pytest.raises(ValueError, match="ffmpeg falhou"):
        transcode(BytesIO(b"nao sou video"), {})
