from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.schemas import JobCreateResponse, JobListResponse, JobStatusResponse, JobSummary


@pytest.mark.parametrize(
    "model",
    [JobCreateResponse, JobStatusResponse, JobSummary, JobListResponse],
)
def test_exemplo_do_schema_e_valido_para_o_modelo(model: type[BaseModel]):
    examples = model.model_json_schema()["examples"]

    assert examples, f"{model.__name__} sem exemplo no schema"
    for example in examples:
        model.model_validate(example)
