#!/bin/bash
set -e

export CRM_INSTANCE_URL="https://insites-mcp-server-v0-1-2-401084637867.australia-southeast1.run.app"

# Use the virtual environment's Python which has requests installed
exec /Users/tanadaeloisa/Documents/module_ai/venv/bin/python3 /Users/tanadaeloisa/Documents/module_ai/local/mcp_proxy.py