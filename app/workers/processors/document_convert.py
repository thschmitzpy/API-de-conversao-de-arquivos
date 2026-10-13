from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.workers.processors.base import ProcessorResult

DOCUMENT_TIMEOUT_SECONDS = 120

_SUPPORTED = "docx, doc, odt, rtf, xlsx, xls, ods, pptx, ppt ou odp"

_RTF_MAGIC = b"{\\rtf"
_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

_OLE2_STREAMS = (
    ("WordDocument".encode("utf-16-le"), "doc"),
    ("PowerPoint Document".encode("utf-16-le"), "ppt"),
    ("Workbook".encode("utf-16-le"), "xls"),
)
_OOXML_DIRS = (
    ("word/", "docx"),
    ("xl/", "xlsx"),
    ("ppt/", "pptx"),
)
_ODF_MIMETYPES = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}


def convert(
        input_stream: BytesIO,
        parameters: dict[str, Any],
) -> ProcessorResult:
    data = input_stream.getvalue()
    source_format = _detect_format(data)

    with tempfile.TemporaryDirectory(prefix="document-convert-") as tmpdir:
        tmp = Path(tmpdir)
        in_path = tmp / f"input.{source_format}"
        out_dir = tmp / "out"
        out_dir.mkdir()
        in_path.write_bytes(data)

        profile_uri = (tmp / "profile").as_uri()

        cmd = [
            "soffice",
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to", "pdf",
            "--outdir", str(out_dir),
            str(in_path),
        ]

        started = time.monotonic()
        result = _run_soffice(cmd)
        elapsed = time.monotonic() - started

        out_path = out_dir / "input.pdf"
        if result.returncode != 0 or not out_path.exists():
            raise ValueError(
                "LibreOffice nao conseguiu converter o documento: "
                f"{_relevant_output_line(result)}"
            )
        payload = out_path.read_bytes()

    return ProcessorResult(
        output=BytesIO(payload),
        output_content_type="application/pdf",
        output_extension="pdf",
        result_metadata={
            "source_format": source_format,
            "pages": _count_pages(payload),
            "output_size_bytes": len(payload),
            "soffice_duration_seconds": round(elapsed, 2),
        },
    )


def _detect_format(data: bytes) -> str:
    if data.startswith(_RTF_MAGIC):
        return "rtf"

    if data.startswith(_OLE2_MAGIC):
        for marker, fmt in _OLE2_STREAMS:
            if marker in data:
                return fmt
        raise ValueError(
            "arquivo OLE2 nao reconhecido (esperado doc, xls ou ppt)"
        )

    if data.startswith(_ZIP_MAGIC):
        return _detect_zip_format(data)

    raise ValueError(f"formato nao suportado (use {_SUPPORTED})")


def _detect_zip_format(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "mimetype" in names:
                mimetype = (
                    archive.read("mimetype")
                    .decode("ascii", errors="replace")
                    .strip()
                )
                fmt = _ODF_MIMETYPES.get(mimetype)
                if fmt is None:
                    raise ValueError(
                        f"documento OpenDocument nao suportado: '{mimetype}'"
                    )
                return fmt
    except zipfile.BadZipFile as exc:
        raise ValueError(f"arquivo ZIP invalido: {exc}") from exc

    if "[Content_Types].xml" in names:
        for prefix, fmt in _OOXML_DIRS:
            if any(name.startswith(prefix) for name in names):
                return fmt
        raise ValueError(
            "pacote OOXML nao reconhecido (esperado docx, xlsx ou pptx)"
        )

    raise ValueError("ZIP nao e documento Office nem OpenDocument")


def _run_soffice(cmd: list[str]) -> subprocess.CompletedProcess[str]:                     # soffice e um script que dispara o soffice.bin como filho. Nova sessao
                                                                                          # permite matar o grupo inteiro no timeout, sem deixar processo orfao.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=DOCUMENT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise ValueError(
            f"LibreOffice excedeu timeout de {DOCUMENT_TIMEOUT_SECONDS}s"
        ) from exc
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def _relevant_output_line(result: subprocess.CompletedProcess[str]) -> str:
    combined = f"{result.stdout or ''}\n{result.stderr or ''}"
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    for line in lines:
        if line.lower().startswith("error"):
            return line
    return lines[-1] if lines else "erro desconhecido"


def _count_pages(payload: bytes) -> int:
    try:
        return len(PdfReader(BytesIO(payload)).pages)
    except PdfReadError as exc:
        raise ValueError(f"PDF gerado e invalido: {exc}") from exc
