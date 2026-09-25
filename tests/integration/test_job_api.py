from __future__ import annotations

import io
import json
import time
import uuid

import pytest
from PIL import Image

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.storage.minio_client import download_bytes

from tests.integration.conftest import make_png_bytes, object_exists


def test_post_jobs_upload_persiste_e_enfileira(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.api.jobs.celery_app.send_task",
        lambda name, args=None, **kw: calls.append({"name": name, "args": args}),
    )

    png = make_png_bytes()
    response = client.post(
        "/jobs",
        files={"file": ("test.png", png, "image/png")},
        data={
            "operation": "image.thumbnail",
            "parameters": json.dumps({"width": 50}),
        },
    )

    assert response.status_code == 202
    body = response.json()
    job_id = uuid.UUID(body["id"])
    assert body["status"] == "PENDING"
    assert body["status_url"].endswith(f"/jobs/{job_id}")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
        assert job.operation == "image.thumbnail"
        assert job.input_filename == "test.png"
        assert job.parameters == {"width": 50}
        assert job.input_size_bytes == len(png)

    settings = get_settings()
    assert object_exists(settings.minio_bucket_input, f"{job_id}/test.png")

    assert len(calls) == 1
    assert calls[0]["name"] == "app.workers.tasks.process_job"
    assert calls[0]["args"] == [str(job_id)]


def test_post_jobs_rollback_ao_falhar_insert(client, monkeypatch):
    send_task_calls = []
    monkeypatch.setattr(
        "app.api.jobs.celery_app.send_task",
        lambda *a, **kw: send_task_calls.append(a),
    )

    fixed_id = uuid.uuid4()
    monkeypatch.setattr("app.api.jobs.uuid.uuid4", lambda: fixed_id)

    with SessionLocal() as db:
        db.add(
            Job(
                id=fixed_id,
                status=JobStatus.DONE,
                operation="image.thumbnail",
                input_key="pre-existente/x.png",
                input_filename="x.png",
                input_content_type="image/png",
                input_size_bytes=1,
                parameters={},
            )
        )
        db.commit()

    response = client.post(
        "/jobs",
        files={"file": ("test.png", make_png_bytes(), "image/png")},
        data={"operation": "image.thumbnail"},
    )

    assert response.status_code == 500

    settings = get_settings()
    assert not object_exists(
        settings.minio_bucket_input, f"{fixed_id}/test.png"
    )

    assert send_task_calls == []

    with SessionLocal() as db:
        job = db.get(Job, fixed_id)
        assert job.status == JobStatus.DONE
        assert job.input_key == "pre-existente/x.png"


def test_processa_image_thumbnail_end_to_end(client):
    png = make_png_bytes(size=200)

    response = client.post(
        "/jobs",
        files={"file": ("test.png", png, "image/png")},
        data={
            "operation": "image.thumbnail",
            "parameters": json.dumps({"width": 50}),
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    deadline = time.time() + 20
    final = None
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("DONE", "FAILED"):
            final = body
            break
        time.sleep(0.3)

    assert final is not None, "job nao completou em 20s (worker rodando?)"
    assert final["status"] == "DONE", f"job falhou: {final}"
    assert final["output_url"] is not None
    assert final["output_url"].startswith("http")

    settings = get_settings()
    with SessionLocal() as db:
        job = db.get(Job, uuid.UUID(job_id))
        assert job.output_key is not None
        output = download_bytes(settings.minio_bucket_output, job.output_key)

    img = Image.open(output)
    assert img.format == "PNG"
    assert img.width == 50
    assert img.height == 50
