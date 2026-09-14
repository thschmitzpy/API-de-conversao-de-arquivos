from __future__ import annotations

import io
import json
import uuid
from pathlib import PureWindowsPath
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.broker.celery_app import celery_app
from app.config import get_settings
from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import JobCreateResponse, JobStatusResponse
from app.storage.minio_client import (
    delete_object,
    presigned_get_url,
    upload_stream,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _parse_parameters(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"parameters deve ser JSON valido: {exc.msg}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "parameters deve ser um objeto JSON",
        )
    return parsed


def _safe_filename(raw: str) -> str:
    name = PureWindowsPath(raw).name
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nome de arquivo invalido")
    return name


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria um novo job de processamento",
)
def create_job(
    request: Request,
    file: Annotated[UploadFile, File(description="Arquivo a ser processado")],
    operation: Annotated[
        str,
        Form(description="Operacao (ex: image.thumbnail, csv.validate, pdf.extract-text)"),
    ],
    parameters: Annotated[
        str | None,
        Form(description="JSON com parametros especificos da operacao"),
    ] = None,
    callback_url: Annotated[
        str | None,
        Form(description="URL que recebera POST assinado ao concluir"),
    ] = None,
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo sem nome")

    filename = _safe_filename(file.filename)
    content = file.file.read()
    size = len(content)

    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo vazio")
    if size > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Arquivo excede o limite de {limit_mb} MB",
        )

    params_dict = _parse_parameters(parameters)

    settings = get_settings()
    job_id = uuid.uuid4()
    input_key = f"{job_id}/{filename}"
    content_type = file.content_type or "application/octet-stream"

    try:
        upload_stream(
            bucket=settings.minio_bucket_input,
            key=input_key,
            stream=io.BytesIO(content),
            size=size,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Falha ao salvar arquivo no storage",
        ) from exc

    job = Job(
        id=job_id,
        status=JobStatus.PENDING,
        operation=operation,
        input_key=input_key,
        input_filename=filename,
        input_content_type=content_type,
        input_size_bytes=size,
        parameters=params_dict,
        callback_url=callback_url,
    )

    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        try:
            delete_object(settings.minio_bucket_input, input_key)
        except Exception:
            pass
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Falha ao registrar job",
        ) from exc

    celery_app.send_task("app.workers.tasks.process_job", args=[str(job.id)])

    return JobCreateResponse(
        id=job.id,
        status=job.status,
        status_url=str(request.url_for("get_job", job_id=job.id)),
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    name="get_job",
    summary="Consulta o estado de um job",
    responses={404: {"description": "Job nao encontrado"}},
)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job nao encontrado")

    response = JobStatusResponse.model_validate(job)

    if job.output_key:
        settings = get_settings()
        response.output_url = presigned_get_url(
            bucket=settings.minio_bucket_output,
            key=job.output_key,
        )

    return response
