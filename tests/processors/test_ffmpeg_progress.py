from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from app.workers.processors import base, video_transcode
from app.workers.processors.audio_extract import extract
from app.workers.processors.video_transcode import transcode
from app.workers.progress import reporting_progress

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="requer ffmpeg no PATH",
)


@pytest.fixture(scope="module")
def sample_mp4() -> bytes:
    # 5 s para o ffmpeg emitir mais de um bloco de progresso.
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "s.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(out),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return out.read_bytes()


def test_transcode_reporta_progresso_crescente(sample_mp4):
    fracoes: list[float] = []
    with reporting_progress(fracoes.append):
        transcode(BytesIO(sample_mp4), {"format": "webm"})

    assert fracoes
    assert fracoes == sorted(fracoes)
    assert all(0.0 <= f <= 1.0 for f in fracoes)
    assert fracoes[-1] >= 0.9


def test_audio_extract_reporta_progresso(sample_mp4):
    fracoes: list[float] = []
    with reporting_progress(fracoes.append):
        extract(BytesIO(sample_mp4), {"format": "mp3"})

    assert fracoes
    assert fracoes[-1] >= 0.9


def test_sem_callback_converte_normalmente(sample_mp4):
    result = transcode(BytesIO(sample_mp4), {})
    assert result.output.getbuffer().nbytes > 0


def test_timeout_mata_o_ffmpeg(sample_mp4, monkeypatch):
    monkeypatch.setattr(video_transcode, "VIDEO_TIMEOUT_SECONDS", 0)
    with pytest.raises(ValueError, match="timeout"):
        transcode(BytesIO(sample_mp4), {"format": "webm"})


def test_probe_duration_le_a_duracao(sample_mp4, tmp_path):
    path = tmp_path / "input"
    path.write_bytes(sample_mp4)
    assert base._probe_duration(path) == pytest.approx(5.0, abs=0.2)


def test_probe_duration_none_para_arquivo_que_nao_e_midia(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"nao sou um video")
    assert base._probe_duration(path) is None
