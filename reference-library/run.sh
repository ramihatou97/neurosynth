#!/bin/bash
# Run the Neurosurgery Reference Library Application

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Note: ANTHROPIC_API_KEY not set. AI categorization will be disabled."
    echo "To enable AI features, run:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo ""
fi

# Run the application
python main.py
