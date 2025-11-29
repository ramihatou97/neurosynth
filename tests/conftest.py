"""Shared pytest fixtures for NeuroSynth tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings to avoid requiring real API keys in tests."""
    mock_env = {
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "GOOGLE_API_KEY": "test-google-key",
        "VOYAGE_API_KEY": "pa-test-voyage-key",
    }
    with patch.dict(os.environ, mock_env, clear=False):
        # Reset the global settings instance
        import neurosynth.config

        neurosynth.config._settings = None
        yield
        neurosynth.config._settings = None


@pytest.fixture
def sample_source():
    """Create a sample Source object."""
    from neurosynth.models.document import DocumentFormat, Source

    return Source(
        path=Path("/tmp/test.pdf"),
        format=DocumentFormat.PDF,
        title="Test Neurosurgical Chapter",
        authors=["Smith J", "Jones M"],
        year=2023,
    )


@pytest.fixture
def sample_chunks(sample_source):
    """Create sample ContentChunk objects."""
    from neurosynth.models.document import ContentChunk

    return [
        ContentChunk(
            content="The vestibular schwannoma is a benign tumor arising from Schwann cells.",
            source=sample_source,
            page_number=1,
            section_title="Introduction",
        ),
        ContentChunk(
            content="Vestibular schwannomas account for approximately 8% of intracranial tumors.",
            source=sample_source,
            page_number=2,
            section_title="Epidemiology",
        ),
        ContentChunk(
            content="Surgical approaches include retrosigmoid, middle fossa, and translabyrinthine.",
            source=sample_source,
            page_number=10,
            section_title="Surgical Technique",
        ),
    ]


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "sources").mkdir()
    (project / "processed").mkdir()
    (project / "output").mkdir()

    config = 'topic: "Test Topic"\nchunk_size: 1000\n'
    (project / "neurosynth.yaml").write_text(config)

    return project


@pytest.fixture
def mock_claude_response():
    """Mock response from Claude API."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response from Claude")]
    return mock_response


@pytest.fixture
def mock_gemini_response():
    """Mock response from Gemini API."""
    mock_response = MagicMock()
    mock_response.text = "Test response from Gemini"
    return mock_response


@pytest.fixture
def mock_voyage_response():
    """Mock response from Voyage API."""
    import numpy as np

    mock_response = MagicMock()
    mock_response.embeddings = [np.random.rand(1024).tolist() for _ in range(3)]
    return mock_response


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_pdf_path(fixtures_dir):
    """Return path to sample PDF fixture.

    Note: You must add a real PDF file at tests/fixtures/sample_chapter.pdf
    for integration tests to work.
    """
    pdf_path = fixtures_dir / "sample_chapter.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def sample_pdf_with_images(fixtures_dir):
    """Return path to sample PDF with images.

    Note: You must add a real PDF file at tests/fixtures/sample_images.pdf
    for visual integration tests to work.
    """
    pdf_path = fixtures_dir / "sample_images.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF with images not found: {pdf_path}")
    return pdf_path
