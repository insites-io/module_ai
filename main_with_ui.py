# --- File: main_with_ui.py (The MCP Server/API with UI) ---
# This is a FastAPI server that acts as the MCP server and serves a web UI.
# It receives prompts, processes them using a LangChain agent, and streams the response.

import asyncio
import os
import uuid
import json
import uvicorn
# import hashlib
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_google_vertexai import ChatVertexAI # Official LangChain integration for Vertex AI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from collections import defaultdict
from typing import Dict, Any
# from cache_manager import CacheManager

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration ---
# --- IMPORTANT: These environment variables MUST be set in your Cloud Run service or .env file ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
# ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"

# Handle credentials - use local vertex-credentials.json file
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "vertex-credentials.json")
if os.path.exists(CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
    print(f"Using local credentials from: {CREDENTIALS_PATH}")
else:
    # Fallback to environment variable if local file doesn't exist
    env_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = env_credentials
        print(f"Using credentials from environment: {env_credentials}")
    else:
        # In Cloud Run, use the default service account credentials
        print("Using default service account credentials from Cloud Run")

if not all([GCP_PROJECT_ID, GCP_REGION]):
    raise ValueError("GCP_PROJECT_ID and GCP_REGION must be set.")

# --- Asynchronous Message Queues for Streaming ---
# This dictionary holds the message queues for each session_id
message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting MCP CRM Server with UI...")

    # # Initialize cache manager
    # app.state.cache_manager = CacheManager(REDIS_URL, CACHE_TTL_SECONDS)
    # if ENABLE_CACHING:
    #     await app.state.cache_manager.initialize()
    # else:
    #     print("⚠️ Caching disabled")
    #     app.state.cache_manager.is_enabled = False
    
    try:
        print("🔧 Initializing LLM and MCP tools...")
        # Initialize the LLM (Claude on Vertex AI)
        llm = ChatVertexAI(
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
            model_name=GEMINI_MODEL_NAME,
            temperature=0
        )

        # Store the LLM for later use
        app.state.llm = llm
        
        # Create a simple agent without tools initially
        app.state.agent = create_react_agent(llm, [])
        print("✅ LLM agent initialized successfully.")
        
        # Test the LLM connection
        try:
            test_message = await llm.ainvoke("Hello")
            print("✅ LLM connection test successful")
        except Exception as test_error:
            print(f"⚠️ LLM connection test failed: {test_error}")
            # Don't fail startup for this, but log it
            
    except Exception as e:
        print(f"❌ Error initializing LLM: {e}")
        import traceback
        traceback.print_exc()
        # Log the error but don't fail startup completely
        print(f"⚠️ Continuing with startup despite LLM initialization error")
        app.state.llm = None
        app.state.agent = None
    
    yield
    
    # Shutdown (if needed)
    print("🛑 Shutting down MCP CRM Server...")
    try:
        # Clean up any remaining tasks
        for task in asyncio.all_tasks():
            if not task.done():
                print(f"DEBUG: Cancelling task: {task}")
                task.cancel()
    except Exception as cleanup_error:
        print(f"DEBUG: Error during cleanup: {cleanup_error}")

app = FastAPI(
    title="MCP CRM API with UI",
    description="API for CRM operations using MCP protocol and LangChain with web interface",
    version="1.0.0",
    lifespan=lifespan
)

# Global exception handler for unhandled async errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"DEBUG: Global exception handler caught: {exc}")
    import traceback
    traceback.print_exc()
    return {
        "success": False,
        "error": "Internal server error",
        "detail": str(exc),
        "timestamp": "2025-08-11T02:30:00Z"
    }

# --- Mount static files ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Health Check Endpoint ---
@app.get("/")
async def health_check():
    """Health check endpoint for the API service."""
    return {
        "status": "healthy",
        "service": "MCP CRM API with UI",
        "version": "1.0.0",
        "timestamp": "2025-08-11T02:30:00Z",
        "message": "Server is running and ready",
        "ui_url": "/ui"
    }

@app.get("/health")
async def health_check_simple():
    """Simple health check that responds immediately."""
    return {"status": "ok"}

# --- Pure MCP Protocol Endpoint ---
@app.get("/mcp/tools/list", response_class=Response)
async def mcp_tools_list():
    """Pure MCP protocol endpoint that implements tools/list functionality.
    
    This endpoint returns tools in MCP protocol format via GET request.
    For reliability, it always returns fallback tools immediately.
    """
    print("🔍 MCP protocol GET endpoint called - returning fallback tools immediately")
    
    # Define fallback tools - always return these for reliability
    fallback_tools = [
        {
            "name": "get_contacts",
            "description": "Get all contacts from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_relationships",
            "description": "Get contact relationships from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_addresses",
            "description": "Get contact addresses from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_companies",
            "description": "Get all companies from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_relationships",
            "description": "Get company relationships from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_addresses",
            "description": "Get company addresses from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_system_fields",
            "description": "Get system fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_sytem_fields",
            "description": "Get contact custom fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_sytem_fields",
            "description": "Get company custom fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_addresses_by_uuid",
            "description": "Get addresses for a specific contact by UUID",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "The UUID of the contact"
                    }
                },
                "required": ["contact_uuid"]
            }
        },
        {
            "name": "get_contact_by_uuid",
            "description": "Get a specific contact by UUID",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "The UUID of the contact"
                    }
                },
                "required": ["contact_uuid"]
            }
        },
        {
            "name": "save_contact",
            "description": "Save or update a contact in the CRM system",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_data": {
                        "type": "object",
                        "description": "Contact data to save"
                    }
                },
                "required": ["contact_data"]
            }
        },
        {
            "name": "list_available_tools",
            "description": "List all available tools in this MCP CRM server",
            "schema": {"type": "object", "properties": {}}
        }
    ]
    
    # Always return fallback tools immediately for reliability
    response_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": fallback_tools,
            "nextCursor": None
        },
        "note": "Using reliable fallback tool list for immediate response"
    }
    
    print(f"📤 Returning {len(fallback_tools)} fallback tools immediately")
    
    return Response(
        content=json.dumps(response_data, indent=2),
        media_type="application/json",
        status_code=200,
        headers={
            "Cache-Control": "no-cache",
            "Content-Type": "application/json"
        }
    )

# --- UI Endpoint ---
@app.get("/ui")
async def serve_ui():
    """Serve the web UI for the CRM assistant."""
    try:
        with open("static/index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="UI file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving UI: {str(e)}")

# --- API Documentation ---
@app.get("/docs")
async def api_docs():
    """API documentation and usage examples."""
    return {
        "endpoints": {
            "GET /": "Health check",
            "GET /ui": "Web UI for CRM assistant",
            "GET /docs": "This API documentation",
            "GET /tools": "List all available MCP tools (REST wrapper)",
            "GET /mcp/tools/list": "Pure MCP protocol tools/list endpoint",
            "POST /messages": "Send a prompt to the CRM agent (with SSE streaming)",
            "POST /query": "Direct query endpoint (synchronous response)",
            "GET /sse": "Server-Sent Events stream for real-time responses"
        },
        "usage": {
            "GET /ui": {
                "description": "Access the web interface for the CRM assistant",
                "note": "Open this URL in your browser to use the UI"
            },
            "GET /tools": {
                "description": "List all available MCP tools with descriptions and schemas (REST API)",
                "note": "User-friendly REST wrapper around MCP tools/list protocol"
            },
            "GET /mcp/tools/list": {
                "description": "Pure MCP protocol endpoint implementing tools/list JSON-RPC method",
                "note": "For MCP clients and protocol-level integration",
                "example": {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {"cursor": "optional-cursor-value"}
                }
            },
            "POST /messages": {
                "url": "/messages?session_id={session_id}&instance_url={instance_url}&instance_api_key={instance_api_key}",
                "body": {"prompt": "Your CRM query here"},
                "example": "Get me all contacts",
                "note": "Use with SSE endpoint for streaming responses"
            },
            "POST /query": {
                "url": "/query?instance_url={instance_url}&instance_api_key={instance_api_key}",
                "body": {"prompt": "Your CRM query here"},
                "example": "Get me all contacts",
                "note": "Direct response, no streaming required"
            },
            "GET /sse": {
                "url": "/sse?session_id={session_id}&instance_url={instance_url}&instance_api_key={instance_api_key}",
                "description": "Establish SSE connection for streaming responses"
            }
        },
        "mcp_protocol": {
            "description": "This server implements both REST API and MCP protocol endpoints",
            "endpoints": {
                "/tools": "REST wrapper for easy web integration",
                "/mcp/tools/list": "Native MCP protocol implementation"
            },
            "protocol": "JSON-RPC 2.0 with MCP tools/list method",
            "note": "Both endpoints discover the same tools but in different formats"
        },
        "parameters": {
            "session_id": "Unique identifier for the conversation session",
            "instance_url": "Your CRM instance URL",
            "instance_api_key": "Your CRM instance API key"
        }
    }

# --- Tools Test Endpoint (Simple) ---
@app.get("/tools/test")
async def test_tools():
    """Simple test endpoint to verify tools listing works without MCP session."""
    print("🧪 Tools test endpoint called")
    
    test_tools = [
        {
            "name": "get_contacts",
            "description": "Get all contacts from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_companies",
            "description": "Get all companies from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_by_uuid",
            "description": "Get a specific contact by UUID",
            "schema": {
                "type": "object", 
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "The UUID of the contact"
                    }
                },
                "required": ["contact_uuid"]
            }
        },
        {
            "name": "save_contact",
            "description": "Save or update a contact in the CRM system",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_data": {
                        "type": "object",
                        "description": "Contact data to save"
                    }
                },
                "required": ["contact_data"]
            }
        }
    ]
    
    return {
        "success": True,
        "total_tools": len(test_tools),
        "tools": test_tools,
        "message": "Test tools loaded successfully - no MCP session required"
    }

# --- Simple Tools Endpoint (Always Works) ---
@app.get("/tools/simple")
async def simple_tools():
    """Simple tools endpoint that always returns immediately without MCP sessions."""
    print("🔍 Simple tools endpoint called - returning immediately")
    
    simple_tools = [
        {
            "name": "Get Contacts",
            "description": "Get all contacts from the CRM module",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Contact Relationships", 
            "description": "Get contact relationships from the CRM module",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Contact Addresses",
            "description": "Get contact addresses from the CRM module", 
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Companies",
            "description": "Get all companies from the CRM module",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Company Relationships",
            "description": "Get company relationships from the CRM module",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Company Addresses", 
            "description": "Get company addresses from the CRM module",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get System Fields",
            "description": "Get system fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Contact Sytem Fields",
            "description": "Get contact custom fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "Get Company System Fields",
            "description": "Get company custom fields from the CRM system", 
            "schema": {"type": "object", "properties": {}}
        },
        # {
        #     "name": "get_contact_addresses_by_uuid",
        #     "description": "Get addresses for a specific contact by UUID",
        #     "schema": {
        #         "type": "object",
        #         "properties": {
        #             "contact_uuid": {
        #                 "type": "string",
        #                 "description": "The UUID of the contact"
        #             }
        #         },
        #         "required": ["contact_uuid"]
        #     }
        # },
        # {
        #     "name": "get_contact_by_uuid",
        #     "description": "Get a specific contact by UUID",
        #     "schema": {
        #         "type": "object", 
        #         "properties": {
        #             "contact_uuid": {
        #                 "type": "string",
        #                 "description": "The UUID of the contact"
        #             }
        #         },
        #         "required": ["contact_uuid"]
        #     }
        # },
        {
            "name": "save_contact",
            "description": "Save or update a contact in the CRM system",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_data": {
                        "type": "object",
                        "description": "Contact data to save"
                    }
                },
                "required": ["contact_data"]
            }
        },
        # {
        #     "name": "list_available_tools",
        #     "description": "List all available tools in this MCP CRM server",
        #     "schema": {"type": "object", "properties": {}}
        # }
    ]
    
    return {
        "success": True,
        "total_tools": len(simple_tools),
        "tools": simple_tools,
        "message": f"Successfully loaded {len(simple_tools)} tools (simple endpoint)",
        "note": "Tools loaded from simple endpoint - no MCP session required"
    }

# --- Tools Listing Endpoint ---
@app.get("/tools")
async def list_tools(request: Request):
    """List all available MCP tools with their descriptions and parameters."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Path to your CRM MCP server
        crm_server_path = os.path.join(os.path.dirname(__file__), "servers", "crm_server.py")

        # Read instance credentials from query params (optional)
        instance_url = request.query_params.get("instance_url")
        instance_api_key = request.query_params.get("instance_api_key")
        print(f"Instance URL: {instance_url}")
        print(f"Instance API Key: {instance_api_key}")
        # Spawn a new MCP server process via stdio
        server_params = StdioServerParameters(
            command="python",
            args=[crm_server_path, "--instance-url", instance_url, "--instance-api-key", instance_api_key]
        )

        tools_info = []
        async with stdio_client(server_params) as (read, write):
            session = ClientSession(read, write)

            # Load tools from MCP server
            tools = await load_mcp_tools(session)
            for tool in tools:
                tools_info.append({
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.args_schema.schema() if hasattr(tool, "args_schema") else None,
                })

        return {
            "success": True,
            "total_tools": len(tools_info),
            "tools": tools_info,
            "message": f"Successfully loaded {len(tools_info)} MCP tools",
        }

    except Exception as e:
        import traceback
        print(f"❌ Error listing tools: {e}")
        traceback.print_exc()

        return {
            "success": False,
            "error": str(e),
            "message": "Failed to dynamically load tools, check CRM server logs",
        }


def get_fallback_tools_response():
    """Return fallback tools response when MCP protocol fails."""
    fallback_tools = [
        {
            "name": "get_contacts",
            "description": "Get all contacts from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_relationships", 
            "description": "Get contact relationships from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_addresses",
            "description": "Get contact addresses from the CRM system", 
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_companies",
            "description": "Get all companies from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_relationships",
            "description": "Get company relationships from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_addresses", 
            "description": "Get company addresses from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_system_fields",
            "description": "Get system fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_sytem_fields",
            "description": "Get contact custom fields from the CRM system",
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_company_sytem_fields",
            "description": "Get company custom fields from the CRM system", 
            "schema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_contact_addresses_by_uuid",
            "description": "Get addresses for a specific contact by UUID",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "The UUID of the contact"
                    }
                },
                "required": ["contact_uuid"]
            }
        },
        {
            "name": "get_contact_by_uuid",
            "description": "Get a specific contact by UUID",
            "schema": {
                "type": "object", 
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "The UUID of the contact"
                    }
                },
                "required": ["contact_uuid"]
            }
        },
        {
            "name": "save_contact",
            "description": "Save or update a contact in the CRM system",
            "schema": {
                "type": "object",
                "properties": {
                    "contact_data": {
                        "type": "object",
                        "description": "Contact data to save"
                    }
                },
                "required": ["contact_data"]
            }
        },
        {
            "name": "list_available_tools",
            "description": "List all available tools in this MCP CRM server",
            "schema": {"type": "object", "properties": {}}
        }
    ]
    
    return {
        "success": False,
        "error": "MCP protocol failed - using fallback tool list",
        "fallback_tools": fallback_tools,
        "total_tools": len(fallback_tools),
        "message": "Using fallback tool list - MCP tools/list protocol failed",
        "mcp_protocol": "fallback",
        "note": "This is a static fallback when MCP tools/list cannot be reached"
    }

# --- Endpoint to receive the user's prompt ---
@app.post("/messages")
async def handle_prompt(request: Request):
    """Receives a prompt and pushes it to an agent for processing."""
    body = await request.json()
    session_id = request.query_params.get("session_id")
    instance_url = request.query_params.get("instance_url")
    instance_api_key = request.query_params.get("instance_api_key") 
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not instance_url:
        raise HTTPException(status_code=400, detail="instance_url is required")
    if not instance_api_key:
        raise HTTPException(status_code=400, detail="instance_api_key is required")

    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    print(f"Received prompt for session {session_id}: {prompt}")
    print(f"Current message queues: {list(message_queues.keys())}")
    print(f"Session {session_id} exists in queues: {session_id in message_queues}")

    # Start the agent's work in a separate task so the POST request can return quickly
    async def run_agent():
        response_text = ""
        try:
            # Check if LLM is available
            if not hasattr(app.state, 'llm') or app.state.llm is None:
                response_text = "Error: LLM not initialized. Please check server logs."
                return
                
            # Create server parameters with instance variables as command line arguments
            # Use sys.executable to get the current Python interpreter path
            import sys
            import os
            python_path = sys.executable
            script_path = os.path.join(os.getcwd(), "servers", "crm_server.py")
            
            server_args = [python_path, script_path]
            if instance_url:
                server_args.extend(["--instance-url", instance_url])
            if instance_api_key:
                server_args.extend(["--instance-api-key", instance_api_key])
            
            print(f"DEBUG: Starting MCP server with args: {server_args}")
            
            # Debug: Check if the script exists and is executable
            if os.path.exists(script_path):
                print(f"DEBUG: Script exists at {script_path}")
                if os.access(script_path, os.R_OK):
                    print(f"DEBUG: Script is readable")
                else:
                    print(f"DEBUG: Script is NOT readable")
                if os.access(script_path, os.X_OK):
                    print(f"DEBUG: Script is executable")
                else:
                    print(f"DEBUG: Script is NOT executable")
            else:
                print(f"DEBUG: Script does NOT exist at {script_path}")
                # List contents of /app/servers directory
                try:
                    import subprocess
                    result = subprocess.run(["ls", "-la", "/app/servers"], capture_output=True, text=True)
                    print(f"DEBUG: Contents of /app/servers: {result.stdout}")
                except Exception as ls_error:
                    print(f"DEBUG: Could not list /app/servers: {ls_error}")
            
            # Simple test to verify Python and script exist
            print(f"DEBUG: Using Python path: {python_path}")
            print(f"DEBUG: Using script path: {script_path}")
            print(f"DEBUG: Script exists: {os.path.exists(script_path)}")
            print(f"DEBUG: Script readable: {os.access(script_path, os.R_OK)}")
            print(f"DEBUG: Script executable: {os.access(script_path, os.X_OK)}")
            
            stdio_server_params = StdioServerParameters(
                command=python_path,
                args=server_args[1:],  # Remove the first argument (python_path) since it's already in command
            )
            
            print(f"DEBUG: About to start stdio client with params: {stdio_server_params}")
            async with stdio_client(stdio_server_params) as (read, write):
                print(f"DEBUG: stdio client started successfully")
                try:
                    async with ClientSession(read_stream=read, write_stream=write) as session:
                        print(f"DEBUG: ClientSession created")
                        try:
                            await session.initialize()
                            print(f"DEBUG: Session initialized")
                        except Exception as init_error:
                            print(f"DEBUG: Session initialization failed: {init_error}")
                            raise Exception(f"MCP session initialization failed: {init_error}")
                        
                        try:
                            tools = await load_mcp_tools(session)
                            print(f"DEBUG: Loaded {len(tools)} tools")
                        except Exception as tools_error:
                            print(f"DEBUG: Failed to load MCP tools: {tools_error}")
                            raise Exception(f"Failed to load MCP tools: {tools_error}")
                        
                        agent = create_react_agent(app.state.llm, tools)
                        system_prompt = """You are an expert CRM assistant. When presenting data, always provide comprehensive, well-structured responses similar to professional AI assistants.

                            RESPONSE FORMATTING RULES:
                            1. Use clear headers and bullet points for readability
                            2. Include ALL relevant details from the data
                            3. Present information in logical groupings
                            4. Always include UUIDs for future reference
                            5. Highlight important relationships (companies, assignments)
                            6. Use markdown-style formatting for structure

                            For contact data, include:
                            - Full contact details (name, email, phone, company)
                            - System information (UUIDs, creation dates)
                            - Relationships and associations
                            - Any special notes or alerts

                            Be thorough and professional - users expect detailed, actionable information."""
                        enhanced_prompt = f"{system_prompt}\n\nUser request: {prompt}"
                        result = await agent.ainvoke({"messages": [HumanMessage(content=enhanced_prompt)]})
                        response_text = result["messages"][-1].content
                except Exception as session_error:
                    print(f"DEBUG: MCP session error: {session_error}")
                    raise session_error
        except ExceptionGroup as eg:
            import traceback
            print(f"DEBUG: ExceptionGroup occurred: {eg}")
            print(f"DEBUG: ExceptionGroup exceptions: {eg.exceptions}")
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            response_text = f"An error occurred: {eg}"
        except Exception as e:
            import traceback
            print(f"DEBUG: Error occurred: {e}")
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            response_text = f"An error occurred: {e}"
        finally:
            try:
                # Send the full response as one piece for testing
                print(f"DEBUG: Total response length: {len(response_text)}")
                print(f"DEBUG: Response text: {repr(response_text)}")
                print(f"DEBUG: Sending full response to queue")
                await message_queues[session_id].put(response_text)
                
                await message_queues[session_id].put("END_STREAM")
            except Exception as queue_error:
                print(f"DEBUG: Error putting message in queue: {queue_error}")

        print(f"Agent completed for session {session_id}: {response_text}")
    
    # Create task with proper error handling
    task = asyncio.create_task(run_agent())
    
    # Add error handler to the task
    def handle_task_exception(task):
        try:
            task.result()
        except Exception as e:
            print(f"DEBUG: Task exception handled: {e}")
            import traceback
            traceback.print_exc()
    
    task.add_done_callback(handle_task_exception)
    
    return {
        "message": "Request accepted", 
        "session_id": session_id,
        "status": "processing",
        "note": "Use the SSE endpoint to receive the response stream"
    }

# --- Synchronous endpoint for simple queries (without SSE) ---
@app.post("/query")
async def direct_query(request: Request):
    """Direct query endpoint that returns the response immediately (no streaming)."""
    body = await request.json()
    instance_url = request.query_params.get("instance_url")
    instance_api_key = request.query_params.get("instance_api_key")
    
    if not instance_url:
        raise HTTPException(status_code=400, detail="instance_url is required")
    if not instance_api_key:
        raise HTTPException(status_code=400, detail="instance_api_key is required")

    #  # Step 1: Check cache first
    # cache_manager = app.state.cache_manager
    # cached_response = await cache_manager.get_cached_response(
    #     query=request.prompt,
    #     instance_url=request.instance_url,
    #     user_context={"api_key_hash": hashlib.sha256(request.instance_api_key.encode()).hexdigest()[:8]}
    # )
    
    # if cached_response:
    #     return {
    #         "response": cached_response.get("response", ""),
    #         "success": True,
    #         "cached": True,
    #         "cached_at": cached_response.get("cached_at")
    #     }
        
    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    print(f"Direct query: {prompt}")

    try:
        # Check if LLM is available
        if not hasattr(app.state, 'llm') or app.state.llm is None:
            return {
                "success": False,
                "error": "LLM not initialized. Please check server logs.",
                "prompt": prompt,
                "timestamp": "2025-08-11T02:30:00Z"
            }
            
        # Create server parameters with instance variables as command line arguments
        server_args = ["/usr/local/bin/python", "/app/servers/crm_server.py"]
        if instance_url:
            server_args.extend(["--instance-url", instance_url])
        if instance_api_key:
            server_args.extend(["--instance-api-key", instance_api_key])
        
        stdio_server_params = StdioServerParameters(
            command="/usr/local/bin/python",
            args=server_args,
        )
        
        # Create a new MCP session for this request
        async with stdio_client(stdio_server_params) as (read, write):
            try:
                async with ClientSession(read_stream=read, write_stream=write) as session:
                    try:
                        await session.initialize()
                    except Exception as init_error:
                        print(f"DEBUG: Session initialization failed: {init_error}")
                        raise Exception(f"MCP session initialization failed: {init_error}")
                    
                    try:
                        tools = await load_mcp_tools(session)
                    except Exception as tools_error:
                        print(f"DEBUG: Failed to load MCP tools: {tools_error}")
                        raise Exception(f"Failed to load MCP tools: {tools_error}")
                    
                    
                    # Create agent with tools for this request
                    agent = create_react_agent(app.state.llm, tools)
                    
                    # ainvoke returns a dictionary
                    result = await agent.ainvoke(
                        {"messages": [HumanMessage(content=prompt)]}
                    )
                    response_text = result["messages"][-1].content
                    
                    return {
                        "success": True,
                        "response": response_text,
                        "prompt": prompt,
                        "timestamp": "2025-08-11T02:30:00Z"
                    }
            except Exception as session_error:
                print(f"DEBUG: MCP session error: {session_error}")
                raise session_error
                
    except ExceptionGroup as eg:
        import traceback
        print(f"ExceptionGroup in direct query: {eg}")
        print(f"ExceptionGroup exceptions: {eg.exceptions}")
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": f"ExceptionGroup: {eg}",
            "prompt": prompt,
            "timestamp": "2025-08-11T02:30:00Z"
        }
    except Exception as e:
        import traceback
        print(f"Error in direct query: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "prompt": prompt,
            "timestamp": "2025-08-11T02:30:00Z"
        }

# --- Simple SSE Test Endpoint ---
@app.get("/sse/test")
async def test_sse():
    """Simple test endpoint to verify SSE is working."""
    print("🧪 SSE test endpoint called")
    
    async def test_generator():
        yield "data: CONNECTED\n\n"
        await asyncio.sleep(1)
        yield "data: Test message 1\n\n"
        await asyncio.sleep(1)
        yield "data: Test message 2\n\n"
        await asyncio.sleep(1)
        yield "data: END_STREAM\n\n"
    
    return StreamingResponse(test_generator(), media_type="text/event-stream")

# --- Endpoint for Server-Sent Events (SSE) streaming ---
async def sse_generator(session_id: str):
    """Generator to stream events to the client."""
    # Ensure the message queue exists for this session
    if session_id not in message_queues:
        message_queues[session_id] = asyncio.Queue()
        print(f"Created message queue for session {session_id}")

    print(f"Starting SSE stream for session {session_id}")
    
    try:
        # Send an immediate connection confirmation
        yield f"data: CONNECTED\n\n"
        print(f"DEBUG: SSE generator sent CONNECTED message for session {session_id}")

        while True:
            try:
                message = await message_queues[session_id].get()
                print(f"DEBUG: SSE generator received message: {repr(message)}")
                if message == "END_STREAM":
                    print(f"DEBUG: SSE generator received END_STREAM")
                    yield f"data: END_STREAM\n\n"
                    break
                print(f"DEBUG: SSE generator yielding chunk: {repr(message)}")
                # Properly format SSE data - escape newlines and ensure proper formatting
                # Replace newlines with spaces for SSE compatibility
                escaped_message = message.replace('\n', '\\n')
                # escaped_message = message.replace('\n', ' ')
                yield f"data: {escaped_message}\n\n"
                # Add a small delay to ensure the chunk is sent
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                print(f"SSE stream cancelled for session {session_id}")
                break
            except Exception as e:
                print(f"DEBUG: Error in SSE stream for session {session_id}: {e}")
                yield f"data: ERROR: {str(e)}\n\n"
                break
                
    except Exception as e:
        print(f"DEBUG: Critical error in SSE generator for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: CRITICAL_ERROR: {str(e)}\n\n"
    finally:
        print(f"Stream ended for session {session_id}")
        # Clean up the queue
        try:
            if session_id in message_queues:
                del message_queues[session_id]
        except Exception as cleanup_error:
            print(f"DEBUG: Error cleaning up queue for session {session_id}: {cleanup_error}")

@app.get("/sse")
async def sse(request: Request):
    session_id = request.query_params.get("session_id")
    instance_url = request.query_params.get("instance_url")
    instance_api_key = request.query_params.get("instance_api_key")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    return StreamingResponse(sse_generator(session_id), media_type="text/event-stream")

# --- Main entry point ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🌐 Starting server on port {port}")
    print(f"🎨 UI available at: http://localhost:{port}/ui")
    print(f"📚 API docs available at: http://localhost:{port}/docs")
    
    uvicorn.run(
        "main_with_ui:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

