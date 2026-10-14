from __future__ import annotations

from app.operations import Operation
from app.workers.tasks import _PROCESSORS


def test_toda_operation_tem_processor_no_worker():
    missing = set(Operation) - set(_PROCESSORS)

    assert not missing, f"Operation sem processor registrado: {sorted(missing)}"


def test_todo_processor_tem_operation_na_api():
    extra = set(_PROCESSORS) - set(Operation)

    assert not extra, f"Processor fora do enum Operation: {sorted(extra)}"
