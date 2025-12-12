#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting NeuroSynth Deployment...${NC}"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# 1. Start Backend Services
echo -e "\n${BLUE}1. Starting Backend Services (Docker)...${NC}"
echo "Stopping any existing containers..."
docker-compose down --remove-orphans
echo "Building and starting containers..."
docker-compose up -d --build

# Wait for services to be healthy
echo "Waiting for services to initialize..."
sleep 10

# 2. Check/Run Image Reindexing
echo -e "\n${BLUE}2. Checking Image Index...${NC}"
echo -e "${YELLOW}Running reindexing script in Docker (Batch Size: 4)...${NC}"
# Use the worker container to run the script
docker-compose run --rm worker python src/scripts/reindex_images.py

# 3. Launch Frontend
echo -e "\n${BLUE}3. Launching Web Application...${NC}"
echo -e "${GREEN}Services are running!${NC}"
echo -e "API Docs: http://localhost:8000/docs"
echo -e "Web App:  http://localhost:8501"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Check if streamlit is installed
if ! python -c "import streamlit" &> /dev/null; then
    echo "Installing frontend dependencies..."
    pip install streamlit
fi

echo -e "\n${GREEN}Starting Streamlit...${NC}"
streamlit run app.py
