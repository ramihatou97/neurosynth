#!/bin/bash
# NeuroSynth Docker Build Script
# Builds all Docker images with proper tagging and caching

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Set build metadata
export BUILD_DATE="${BUILD_DATE:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}"
export GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}"
export VERSION="${VERSION:-$(git describe --tags --always 2>/dev/null || echo "dev")}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  NeuroSynth Docker Build${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  BUILD_DATE: ${YELLOW}$BUILD_DATE${NC}"
echo -e "  GIT_SHA:    ${YELLOW}$GIT_SHA${NC}"
echo -e "  VERSION:    ${YELLOW}$VERSION${NC}"
echo ""

# Build all services
echo -e "${GREEN}Building Docker images...${NC}"

docker compose build \
    --build-arg BUILD_DATE="$BUILD_DATE" \
    --build-arg GIT_SHA="$GIT_SHA" \
    --build-arg VERSION="$VERSION" \
    "$@"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Images built:"
docker images | grep -E "neurosynth|REPOSITORY" | head -10
echo ""
echo -e "To start services: ${YELLOW}docker compose up -d${NC}"
echo -e "To view logs:      ${YELLOW}docker compose logs -f${NC}"
