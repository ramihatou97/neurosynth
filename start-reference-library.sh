#!/bin/bash
# Start Reference Library Desktop Application
# This is the entry point for the NeuroSynth workflow

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         NeuroSynth Reference Library - Research           ║${NC}"
echo -e "${BLUE}║          Neurosurgical Knowledge Synthesis System          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REF_LIB_DIR="$SCRIPT_DIR/reference-library"

# Check if reference library exists
if [ ! -d "$REF_LIB_DIR" ]; then
    echo -e "${YELLOW}⚠️  Error: reference-library directory not found${NC}"
    echo "Expected at: $REF_LIB_DIR"
    exit 1
fi

cd "$REF_LIB_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Verify dependencies
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Check for required packages
if ! python -c "import customtkinter" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing missing dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check for API key (graceful degradation)
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}ℹ️  Note: ANTHROPIC_API_KEY not set${NC}"
    echo "   AI categorization will be disabled"
    echo "   To enable: export ANTHROPIC_API_KEY='your-key'"
    echo
fi

# Display workflow reminder
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Workflow:${NC}"
echo "  1️⃣  Search & filter your reference library"
echo "  2️⃣  Select relevant pages for your topic"
echo "  3️⃣  Click 'Synthesize' → NeuroSynth generates chapter"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Launch the application
echo -e "${GREEN}🚀 Starting Reference Library...${NC}"
echo

exec python main.py
