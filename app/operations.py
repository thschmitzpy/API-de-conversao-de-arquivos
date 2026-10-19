from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class Operation(StrEnum):
    IMAGE_THUMBNAIL = "image.thumbnail"
    CSV_VALIDATE = "csv.validate"
    EXCEL_TO_CSV = "excel.to-csv"
    PDF_EXTRACT_TEXT = "pdf.extract-text"
    PDF_MERGE = "pdf.merge"
    PDF_WATERMARK = "pdf.watermark"
    VIDEO_TRANSCODE = "video.transcode"
    AUDIO_EXTRACT = "audio.extract"
    OCR_EXTRACT = "ocr.extract"
    DOCUMENT_CONVERT = "document.convert"


PARAMETER_EXAMPLES: dict[Operation, dict[str, Any]] = {
    Operation.IMAGE_THUMBNAIL: {"width": 256, "height": 256, "format": "webp", "quality": 85},
    Operation.CSV_VALIDATE: {
        "columns": [
            {"name": "email", "type": "string", "pattern": "^.+@.+$"},
            {"name": "idade", "type": "int", "min": 0, "max": 120, "required": False},
        ],
        "mode": "report",
    },
    Operation.EXCEL_TO_CSV: {"sheet": "Vendas", "delimiter": ";", "include_header": True},
    Operation.PDF_EXTRACT_TEXT: {"pages": "1-3,5", "output_format": "json"},
    Operation.PDF_MERGE: {"order": ["capa.pdf", "relatorio.pdf"]},
    Operation.PDF_WATERMARK: {
        "text": "CONFIDENCIAL",
        "position": "diagonal",
        "opacity": 0.3,
        "color": "red",
    },
    Operation.VIDEO_TRANSCODE: {"format": "webm", "resolution": "720p", "crf": 23},
    Operation.AUDIO_EXTRACT: {"format": "mp3", "bitrate": "192k", "channels": 2},
    Operation.OCR_EXTRACT: {"lang": "por+eng", "output_format": "text", "dpi": 300},
    Operation.DOCUMENT_CONVERT: {},
}


def parameter_examples_markdown() -> str:
    lines = ["| `operation` | Exemplo de `parameters` |", "|---|---|"]
    for operation, example in PARAMETER_EXAMPLES.items():
        payload = f"`{json.dumps(example, ensure_ascii=False)}`" if example else "— (sem parametros)"
        lines.append(f"| `{operation}` | {payload} |")
    return "\n".join(lines)
