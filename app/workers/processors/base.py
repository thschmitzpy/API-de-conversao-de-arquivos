from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol


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
