from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from app.workers.processors.audio_extract import extract

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


def _probe_audio(data: bytes, ext: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"probe.{ext}"
        p.write_bytes(data)
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels",
                "-of", "json",
                str(p),
            ],
            capture_output=True, text=True, check=True,
        )
        return json.loads(r.stdout)["streams"][0]


def test_extract_mp3_default(sample_mp4):
    result = extract(BytesIO(sample_mp4), {})

    assert result.output_extension == "mp3"
    assert result.output_content_type == "audio/mpeg"
    assert _probe_audio(result.output.getvalue(), "mp3")["codec_name"] == "mp3"


def test_extract_wav(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"format": "wav"})

    assert result.output_extension == "wav"
    assert result.output_content_type == "audio/wav"
    assert _probe_audio(result.output.getvalue(), "wav")["codec_name"] == "pcm_s16le"


def test_extract_ogg(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"format": "ogg"})

    assert result.output_extension == "ogg"
    assert result.output_content_type == "audio/ogg"
    assert _probe_audio(result.output.getvalue(), "ogg")["codec_name"] == "vorbis"


def test_extract_aac(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"format": "aac"})

    assert result.output_extension == "aac"
    assert result.output_content_type == "audio/aac"
    assert _probe_audio(result.output.getvalue(), "aac")["codec_name"] == "aac"


def test_bitrate_customizado(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"bitrate": "128k"})

    assert result.result_metadata["bitrate"] == "128k"


def test_sample_rate_customizado(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"sample_rate": 22050})

    probe = _probe_audio(result.output.getvalue(), "mp3")
    assert int(probe["sample_rate"]) == 22050


def test_channels_mono(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"channels": 1})

    assert _probe_audio(result.output.getvalue(), "mp3")["channels"] == 1


def test_channels_stereo(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"channels": 2})

    assert _probe_audio(result.output.getvalue(), "mp3")["channels"] == 2


def test_metadata_reflete_parametros(sample_mp4):
    result = extract(
        BytesIO(sample_mp4),
        {"format": "mp3", "bitrate": "256k", "sample_rate": 44100, "channels": 1},
    )

    meta = result.result_metadata
    assert meta["format"] == "mp3"
    assert meta["bitrate"] == "256k"
    assert meta["sample_rate"] == 44100
    assert meta["channels"] == 1
    assert meta["output_size_bytes"] > 0
    assert meta["ffmpeg_duration_seconds"] >= 0


def test_wav_metadata_bitrate_none(sample_mp4):
    result = extract(BytesIO(sample_mp4), {"format": "wav"})

    assert result.result_metadata["bitrate"] is None


def test_format_invalido_raises(sample_mp4):
    with pytest.raises(ValueError, match="format"):
        extract(BytesIO(sample_mp4), {"format": "flac"})


def test_wav_com_bitrate_raises(sample_mp4):
    with pytest.raises(ValueError, match="bitrate"):
        extract(BytesIO(sample_mp4), {"format": "wav", "bitrate": "192k"})


def test_bitrate_invalido_raises(sample_mp4):
    with pytest.raises(ValueError, match="bitrate"):
        extract(BytesIO(sample_mp4), {"bitrate": "999k"})


def test_sample_rate_nao_int_raises(sample_mp4):
    with pytest.raises(ValueError, match="sample_rate"):
        extract(BytesIO(sample_mp4), {"sample_rate": "44100"})


def test_sample_rate_fora_do_set_raises(sample_mp4):
    with pytest.raises(ValueError, match="sample_rate"):
        extract(BytesIO(sample_mp4), {"sample_rate": 11025})


def test_sample_rate_bool_raises(sample_mp4):
    with pytest.raises(ValueError, match="sample_rate"):
        extract(BytesIO(sample_mp4), {"sample_rate": True})


def test_channels_fora_do_set_raises(sample_mp4):
    with pytest.raises(ValueError, match="channels"):
        extract(BytesIO(sample_mp4), {"channels": 3})


def test_channels_nao_int_raises(sample_mp4):
    with pytest.raises(ValueError, match="channels"):
        extract(BytesIO(sample_mp4), {"channels": "2"})


def test_channels_bool_raises(sample_mp4):
    with pytest.raises(ValueError, match="channels"):
        extract(BytesIO(sample_mp4), {"channels": True})


def test_input_invalido_raises():
    with pytest.raises(ValueError, match="ffmpeg falhou"):
        extract(BytesIO(b"nao sou audio nem video"), {})
