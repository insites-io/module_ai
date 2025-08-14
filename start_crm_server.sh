#!/bin/bash

# Startup script for CRM MCP Server to use with Claude Desktop
# This script sets up environment variables and starts the server

set -e

echo "🚀 Starting CRM MCP Server for Claude Desktop..."

# Check if environment variables are set
if [ -z "$CRM_INSTANCE_URL" ]; then
    echo "⚠️  CRM_INSTANCE_URL not set. Please set this environment variable."
    echo "   export CRM_INSTANCE_URL='https://your-crm-instance.com'"
    exit 1
fi

if [ -z "$CRM_INSTANCE_API_KEY" ]; then
    echo "⚠️  CRM_INSTANCE_API_KEY not set. Please set this environment variable."
    echo "   export CRM_INSTANCE_API_KEY='your-api-key-here'"
    exit 1
fi

echo "✅ CRM Instance URL: $CRM_INSTANCE_URL"
echo "✅ API Key: ${CRM_INSTANCE_API_KEY:0:8}..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
if ! python -c "import mcp" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

echo "🔌 Starting MCP server in stdio mode..."
echo "   This server is now ready to be used with Claude Desktop!"
echo "   Make sure to configure Claude Desktop to use this server."

# Start the server
exec python servers/crm_server.py


