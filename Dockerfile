# NeuroSynth Dockerfile with LaTeX support
# Multi-stage build for smaller final image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Stage 1.5: Tester
FROM builder as tester
RUN pip install --no-cache-dir -e ".[dev]"
COPY tests/ ./tests/
CMD ["python", "-m", "pytest", "tests/"]

# Stage 2: Runtime with LaTeX
FROM python:3.11-slim

WORKDIR /app

# Install LaTeX and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-science \
    latexmk \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Install the package
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p /data/sources /data/processed /data/output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

# Create non-root user for security
RUN useradd -m -u 1000 neurosynth && \
    chown -R neurosynth:neurosynth /app /data

USER neurosynth

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD neurosynth version || exit 1

# Default command
ENTRYPOINT ["neurosynth"]
CMD ["--help"]
