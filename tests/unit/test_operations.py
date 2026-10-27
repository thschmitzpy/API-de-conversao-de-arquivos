from __future__ import annotations

from app.operations import PARAMETER_EXAMPLES, Operation, parameter_examples_markdown
from app.workers.tasks import _PROCESSORS

def test_toda_operation_tem_processor_no_worker():
    missing = set(Operation) - set(_PROCESSORS)

    assert not missing, f"Operation sem processor registrado: {sorted(missing)}"


def test_todo_processor_tem_operation_na_api():
    extra = set(_PROCESSORS) - set(Operation)

    assert not extra, f"Processor fora do enum Operation: {sorted(extra)}"


def test_toda_operation_tem_exemplo_de_parameters():
    missing = set(Operation) - set(PARAMETER_EXAMPLES)

    assert not missing, f"Operation sem exemplo de parameters: {sorted(missing)}"


def test_tabela_de_exemplos_lista_todas_as_operations():
    markdown = parameter_examples_markdown()

    for operation in Operation:
        assert f"`{operation}`" in markdown
