from __future__ import annotations

from enum import StrEnum


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
