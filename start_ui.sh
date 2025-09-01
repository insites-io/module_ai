#!/bin/bash

# Startup script for MCP CRM Server with UI
# This script sets up environment variables and starts the server with web interface

set -e

echo "🚀 Starting MCP CRM Server with UI..."

# Check if environment variables are set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "⚠️  GCP_PROJECT_ID not set. Please set this environment variable."
    echo "   export GCP_PROJECT_ID='your-project-id'"
    exit 1
fi

if [ -z "$GCP_REGION" ]; then
    echo "⚠️  GCP_REGION not set. Please set this environment variable."
    echo "   export GCP_REGION='australia-southeast1'"
    exit 1
fi

echo "✅ GCP Project ID: $GCP_PROJECT_ID"
echo "✅ GCP Region: $GCP_REGION"

# Check if credentials file exists
if [ ! -f "vertex-credentials.json" ]; then
    echo "⚠️  vertex-credentials.json not found. Please ensure your Google Cloud credentials are available."
    echo "   You can set GOOGLE_APPLICATION_CREDENTIALS environment variable to point to your credentials file."
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if static directory and index.html exist
if [ ! -d "static" ]; then
    echo "❌ static directory not found. Creating it..."
    mkdir -p static
fi

if [ ! -f "static/index.html" ]; then
    echo "❌ static/index.html not found. Please ensure the UI file exists."
    exit 1
fi

echo "🔌 Starting MCP server with UI..."
echo "   Web UI will be available at: http://localhost:8080/ui"
echo "   API documentation at: http://localhost:8080/docs"
echo "   Health check at: http://localhost:8080/"

# Start the server
exec python main_with_ui.py


