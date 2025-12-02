"""Job management endpoints."""

import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import redis.asyncio as redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from neurosynth.api.deps import get_redis, get_settings
from neurosynth.api.models.job import (
    JobConfig,
    JobListResponse,
    JobProgress,
    JobResponse,
    JobStatus,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


# Redis key patterns
def job_key(job_id: str) -> str:
    return f"jobs:{job_id}"


def job_status_key(job_id: str) -> str:
    return f"jobs:{job_id}:status"


def job_meta_key(job_id: str) -> str:
    return f"jobs:{job_id}:meta"


QUEUE_KEY = "jobs:queue"


def validate_pdf_file(file_path: Path) -> tuple[bool, str]:
    """Validate PDF file before serving.

    Args:
        file_path: Path to PDF file

    Returns:
        (is_valid, error_message)
    """
    # Check file exists
    if not file_path.exists():
        return False, "File not found"

    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        return False, "File is empty"
    if file_size < 1024:
        return False, f"File too small ({file_size} bytes)"

    # Check PDF magic bytes
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
            if header != b"%PDF-":
                return False, f"Invalid PDF header (found: {header})"

            # Check for EOF marker in last 1KB
            f.seek(max(0, file_size - 1024))
            tail = f.read()
            if b"%%EOF" not in tail:
                return False, "Missing PDF EOF marker"

    except Exception as e:
        return False, f"Error reading file: {e}"

    return True, ""


async def _get_job(job_id: str, redis_client: redis.Redis) -> dict | None:
    """Get job data from Redis."""
    data = await redis_client.hgetall(job_key(job_id))
    if not data:
        return None
    return data


async def _job_to_response(job_id: str, data: dict) -> JobResponse:
    """Convert Redis job data to JobResponse."""
    config = JobConfig(**json.loads(data.get("config", "{}")))

    progress = None
    if data.get("progress"):
        progress = JobProgress(**json.loads(data["progress"]))

    return JobResponse(
        job_id=job_id,
        status=JobStatus(data.get("status", "queued")),
        topic=data.get("topic", ""),
        progress=progress,
        config=config,
        created_at=datetime.fromisoformat(
            data.get("created_at", datetime.utcnow().isoformat())
        ),
        started_at=(
            datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None
        ),
        completed_at=(
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        ),
        error=data.get("error"),
        output_path=data.get("output_path"),
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    files: list[UploadFile] = File(..., description="Source documents to process"),
    topic: str = Form(..., description="Topic name for the chapter"),
    output_format: str = Form(default="latex", description="Output format"),
    chunk_size: int = Form(default=1000, ge=100, le=5000),
    similarity_threshold: float = Form(default=0.92, ge=0.5, le=1.0),
    use_cache: bool = Form(default=True),
    redis_client: redis.Redis = Depends(get_redis),
) -> JobResponse:
    """Create a new synthesis job.

    Upload source documents and configuration to start a synthesis job.
    The job will be queued and processed by a worker.
    """
    settings = get_settings()

    # Validate files
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    supported_extensions = {".pdf", ".epub", ".docx", ".doc", ".txt", ".md"}
    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: {supported_extensions}",
            )

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job directory
    job_dir = Path(settings.jobs_data_dir) / job_id
    sources_dir = job_dir / "sources"
    output_dir = job_dir / "output"
    sources_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    for file in files:
        file_path = sources_dir / (file.filename or f"file_{uuid.uuid4()}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

    # Create job config
    config = JobConfig(
        topic=topic,
        output_format=output_format,
        chunk_size=chunk_size,
        similarity_threshold=similarity_threshold,
        use_cache=use_cache,
    )

    # Store job in Redis
    now = datetime.utcnow().isoformat()
    job_data = {
        "status": JobStatus.QUEUED.value,
        "topic": topic,
        "config": config.model_dump_json(),
        "created_at": now,
        "job_dir": str(job_dir),
        "sources_dir": str(sources_dir),
        "output_dir": str(output_dir),
    }

    await redis_client.hset(job_key(job_id), mapping=job_data)

    # Add to queue
    await redis_client.rpush(QUEUE_KEY, job_id)

    return await _job_to_response(job_id, job_data)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: JobStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    redis_client: redis.Redis = Depends(get_redis),
) -> JobListResponse:
    """List all jobs, optionally filtered by status."""
    # Get all job keys
    keys = []
    async for key in redis_client.scan_iter(match="jobs:*", count=100):
        # Only get top-level job keys (not :status or :meta)
        if key.count(":") == 1:
            keys.append(key)

    jobs = []
    for key in sorted(keys, reverse=True):  # Newest first
        job_id = key.split(":")[1]
        data = await _get_job(job_id, redis_client)
        if data:
            # Filter by status if specified
            if status and data.get("status") != status.value:
                continue
            jobs.append(await _job_to_response(job_id, data))

    total = len(jobs)
    jobs = jobs[offset : offset + limit]

    return JobListResponse(jobs=jobs, total=total)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    redis_client: redis.Redis = Depends(get_redis),
) -> JobResponse:
    """Get job status and details."""
    data = await _get_job(job_id, redis_client)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return await _job_to_response(job_id, data)


@router.get("/{job_id}/output")
async def get_job_output(
    job_id: str,
    redis_client: redis.Redis = Depends(get_redis),
) -> FileResponse:
    """Download the output file for a completed job.

    Validates PDF integrity before serving to prevent corrupted downloads.
    """
    data = await _get_job(job_id, redis_client)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if data.get("status") != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {data.get('status')}",
        )

    output_path = data.get("output_path")
    if not output_path:
        raise HTTPException(
            status_code=404,
            detail="Output file path not set. Job may have failed during finalization.",
        )

    file_path = Path(output_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Output file not found at: {output_path}",
        )

    # Validate PDF if it's a PDF file
    if output_path.endswith(".pdf"):
        is_valid, error_msg = validate_pdf_file(file_path)
        if not is_valid:
            logger.error(f"Job {job_id} completed but PDF is invalid: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Generated PDF file is corrupted: {error_msg}. Please contact support.",
            )

    media_type = (
        "application/pdf"
        if output_path.endswith(".pdf")
        else "application/octet-stream"
    )

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=file_path.name,
    )


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: str,
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    """Cancel a pending or running job."""
    data = await _get_job(job_id, redis_client)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    current_status = data.get("status")
    if current_status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {current_status}",
        )

    # Update status to cancelled
    await redis_client.hset(job_key(job_id), "status", JobStatus.CANCELLED.value)

    # Remove from queue if still queued
    await redis_client.lrem(QUEUE_KEY, 0, job_id)


@router.delete("/{job_id}/data", status_code=204)
async def delete_job_data(
    job_id: str,
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    """Delete job data including files."""
    data = await _get_job(job_id, redis_client)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Delete job directory
    job_dir = data.get("job_dir")
    if job_dir and Path(job_dir).exists():
        shutil.rmtree(job_dir)

    # Delete Redis keys
    await redis_client.delete(job_key(job_id))
