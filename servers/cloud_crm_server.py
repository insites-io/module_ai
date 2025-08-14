import asyncio
import requests
import os
import json
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Configuration from environment variables
INSTANCE_URL = os.getenv('CRM_INSTANCE_URL')
INSTANCE_API_KEY = os.getenv('CRM_INSTANCE_API_KEY')

# FastAPI app
app = FastAPI(
    title="Cloud CRM MCP Server",
    description="MCP-compatible CRM server for cloud deployment",
    version="1.0.0"
)

# Pydantic models for MCP protocol
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int
    method: str
    params: Dict[str, Any] = {}

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: int
    result: Dict[str, Any] = None
    error: Dict[str, Any] = None

class MCPError(BaseModel):
    code: int
    message: str
    data: Dict[str, Any] = None

# Utility: API Request
def fetch_api_data(endpoint: str) -> Dict[str, Any]:
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables."
        }

    url = f"{INSTANCE_URL}{endpoint}"
    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            return {"success": True, "result": response.json()}
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out after 30 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# MCP Tool definitions
MCP_TOOLS = {
    "get_contacts": {
        "name": "get_contacts",
        "description": "Fetch a list of contacts from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_companies": {
        "name": "get_companies", 
        "description": "Fetch a list of companies from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_contact_relationships": {
        "name": "get_contact_relationships",
        "description": "Fetch a list of contacts relationships from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_company_relationships": {
        "name": "get_company_relationships",
        "description": "Fetch a list of company relationships from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_contact_addresses": {
        "name": "get_contact_addresses",
        "description": "Fetch a list of contacts addresses from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_company_addresses": {
        "name": "get_company_addresses",
        "description": "Fetch a list of company addresses from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_system_fields": {
        "name": "get_system_fields",
        "description": "Fetch a list of system fields from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_contact_system_fields": {
        "name": "get_contact_system_fields",
        "description": "Fetch a list of contact system fields from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "get_company_system_fields": {
        "name": "get_company_system_fields",
        "description": "Fetch a list of company system fields from an external API endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

# MCP Protocol Handlers
@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    """Handle MCP protocol requests"""
    
    if request.method == "initialize":
        # MCP initialization
        return MCPResponse(
            id=request.id,
            result={
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "cloud-crm-server",
                    "version": "1.0.0"
                }
            }
        )
    
    elif request.method == "tools/list":
        # Return list of available tools
        tools = list(MCP_TOOLS.values())
        return MCPResponse(
            id=request.id,
            result={"tools": tools}
        )
    
    elif request.method == "tools/call":
        # Execute a tool
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if tool_name not in MCP_TOOLS:
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=-32601,
                    message=f"Tool '{tool_name}' not found"
                ).dict()
            )
        
        # Execute the tool
        try:
            if tool_name == "get_contacts":
                result = fetch_api_data("/crm/api/v2/contacts")
            elif tool_name == "get_companies":
                result = fetch_api_data("/crm/api/v2/companies")
            elif tool_name == "get_contact_relationships":
                result = fetch_api_data("/crm/api/v2/contacts/relationships")
            elif tool_name == "get_company_relationships":
                result = fetch_api_data("/crm/api/v2/companies/relationships")
            elif tool_name == "get_contact_addresses":
                result = fetch_api_data("/crm/api/v2/contacts/addresses")
            elif tool_name == "get_company_addresses":
                result = fetch_api_data("/crm/api/v2/companies/addresses")
            elif tool_name == "get_system_fields":
                result = fetch_api_data("/crm/api/v2/system-fields")
            elif tool_name == "get_contact_system_fields":
                result = fetch_api_data("/crm/api/v2/custom-fields/contacts")
            elif tool_name == "get_company_system_fields":
                result = fetch_api_data("/crm/api/v2/custom-fields/companies")
            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
            
            return MCPResponse(
                id=request.id,
                result={"content": [{"type": "text", "text": str(result)}]}
            )
            
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error=MCPError(
                    code=-32603,
                    message=f"Internal error: {str(e)}"
                ).dict()
            )
    
    else:
        # Unknown method
        return MCPResponse(
            id=request.id,
            error=MCPError(
                code=-32601,
                message=f"Method '{request.method}' not found"
            ).dict()
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Cloud CRM MCP Server",
        "version": "1.0.0",
        "crm_configured": bool(INSTANCE_URL and INSTANCE_API_KEY)
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "service": "Cloud CRM MCP Server",
        "version": "1.0.0",
        "description": "MCP-compatible CRM server for cloud deployment",
        "endpoints": {
            "POST /mcp": "MCP protocol endpoint",
            "GET /health": "Health check",
            "GET /": "This information"
        },
        "crm_configured": bool(INSTANCE_URL and INSTANCE_API_KEY)
    }

if __name__ == "__main__":
    # Check configuration
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        print("Warning: CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY not set.")
        print("Server will start but CRM tools will not work.")
    
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)


