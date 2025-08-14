#!/bin/bash

# Startup script for MCP CRM Server
# This ensures proper port handling for Cloud Run

set -e

# Get the port from environment variable, default to 8080
PORT=${PORT:-8080}

echo "🚀 Starting MCP CRM Server on port $PORT"

# Check if vertex-credentials.json exists
if [ -f "/app/vertex-credentials.json" ]; then
    echo "✅ Credentials file found"
else
    echo "⚠️  Credentials file not found at /app/vertex-credentials.json"
fi

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port $PORT
