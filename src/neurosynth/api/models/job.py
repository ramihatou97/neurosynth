"""Job models for API requests and responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobConfig(BaseModel):
    """Configuration for a synthesis job."""

    topic: str = Field(..., description="Topic name for the chapter")
    output_format: str = Field(
        default="latex", description="Output format (latex, markdown)"
    )
    chunk_size: int = Field(
        default=1000, description="Chunk size for document processing"
    )
    similarity_threshold: float = Field(
        default=0.92, description="Similarity threshold for deduplication"
    )
    use_cache: bool = Field(default=True, description="Use embedding cache")


class JobCreate(BaseModel):
    """Request model for creating a new job."""

    topic: str = Field(..., description="Topic name for the chapter")
    output_format: str = Field(
        default="latex", description="Output format (latex, markdown)"
    )
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    similarity_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    use_cache: bool = Field(default=True)

    def to_config(self) -> JobConfig:
        """Convert to JobConfig."""
        return JobConfig(
            topic=self.topic,
            output_format=self.output_format,
            chunk_size=self.chunk_size,
            similarity_threshold=self.similarity_threshold,
            use_cache=self.use_cache,
        )


class JobProgress(BaseModel):
    """Progress information for a running job."""

    stage: str = Field(..., description="Current processing stage")
    message: str = Field(..., description="Progress message")
    percent: float | None = Field(None, description="Progress percentage (0-100)")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobResponse(BaseModel):
    """Response model for job status."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    topic: str = Field(..., description="Job topic")
    progress: JobProgress | None = Field(None, description="Current progress")
    config: JobConfig = Field(..., description="Job configuration")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Processing start timestamp")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    error: str | None = Field(None, description="Error message if failed")
    output_path: str | None = Field(
        None, description="Path to output file if completed"
    )


class JobListResponse(BaseModel):
    """Response model for listing jobs."""

    jobs: list[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
