# Deep-Dx ColBERT Docker Container
# Isolated environment for ColBERT to avoid dependency conflicts

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies in correct order (critical for ColBERT)
RUN pip install --no-cache-dir torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir faiss-cpu==1.7.4
RUN pip install --no-cache-dir ninja

# Pin LangChain ecosystem to avoid conflicts
RUN pip install --no-cache-dir \
    langchain==0.1.20 \
    langchain-core==0.1.52 \
    langchain-community==0.0.38 \
    langchain-text-splitters==0.0.1

# Install RAGatouille (ColBERT wrapper)
RUN pip install --no-cache-dir ragatouille==0.0.8

# Install additional utilities
RUN pip install --no-cache-dir \
    numpy \
    tqdm

# Copy scripts
COPY scripts/ /app/scripts/

# Create data directory
RUN mkdir -p /app/data /tmp

# Default command - keep container alive
CMD ["tail", "-f", "/dev/null"]
