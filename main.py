import asyncio
import os
import uuid
import json
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_google_vertexai import ChatVertexAI
from collections import defaultdict
from typing import Dict, Any, Optional
import httpx
from pydantic import BaseModel

# Import CRM tools directly
from servers.crm_tools import CRMTools

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration with graceful defaults for build-time ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION") 
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")

# Handle credentials
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "vertex-credentials.json")
if os.path.exists(CREDENTIALS_PATH):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
    print(f"Using local credentials from: {CREDENTIALS_PATH}")
else:
    env_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = env_credentials
        print(f"Using credentials from environment: {env_credentials}")
    else:
        print("Using default service account credentials from Cloud Run")

# Only validate required vars if not in build mode (when they're actually needed)
def validate_environment():
    """Validate environment variables when actually needed."""
    if not all([GCP_PROJECT_ID, GCP_REGION]):
        raise ValueError("GCP_PROJECT_ID and GCP_REGION must be set.")

# --- Asynchronous Message Queues for Streaming ---
message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

# --- Pydantic Models ---
class QueryRequest(BaseModel):
    prompt: str
    instance_url: str
    instance_api_key: str

class MessageRequest(BaseModel):
    prompt: str
    instance_url: str
    instance_api_key: str

class ToolsRequest(BaseModel):
    instance_url: str
    instance_api_key: str

# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting MCP CRM Server...")
    
    # Validate environment at startup (runtime)
    try:
        validate_environment()
        print(f"📋 Project ID: {GCP_PROJECT_ID}")
        print(f"🌍 Region: {GCP_REGION}")
        print(f"🤖 Model: {GEMINI_MODEL_NAME}")
    except ValueError as e:
        print(f"❌ Environment validation failed: {e}")
        app.state.llm = None
        yield
        return
    
    try:
        print("🔧 Initializing LLM...")
        # Initialize the LLM
        llm = ChatVertexAI(
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
            model_name=GEMINI_MODEL_NAME,
            temperature=0,
        )

        # Store the LLM for later use
        app.state.llm = llm
        print("✅ LLM initialized successfully.")
        
        # Test the LLM connection
        try:
            test_message = await llm.ainvoke("Hello")
            print("✅ LLM connection test successful")
        except Exception as test_error:
            print(f"⚠️ LLM connection test failed: {test_error}")
            
    except Exception as e:
        print(f"❌ Error initializing LLM: {e}")
        import traceback
        traceback.print_exc()
        app.state.llm = None
    
    yield
    
    # Shutdown
    print("🛑 Shutting down MCP CRM Server...")

app = FastAPI(
    title="MCP CRM API",
    description="API for CRM operations using direct tool imports",
    version="1.0.0",
    lifespan=lifespan
)

# --- Helper function to create CRM tools ---
def create_crm_tools(instance_url: str, instance_api_key: str):
    """Create CRM tools with the given instance credentials."""
    crm_tools = CRMTools(instance_url, instance_api_key)
    return crm_tools.get_langchain_tools()

# --- Health Check Endpoint ---
@app.get("/")
async def health_check():
    """Health check endpoint for the API service."""
    return {
        "status": "healthy",
        "service": "MCP CRM API",
        "version": "1.0.0",
        "message": "Server is running and ready",
        "config": {
            "project_id": GCP_PROJECT_ID or "not set",
            "region": GCP_REGION or "not set",
            "model": GEMINI_MODEL_NAME
        }
    }

@app.get("/health")
async def health_check_simple():
    """Simple health check that responds immediately."""
    return {"status": "ok"}

# --- API Documentation ---
@app.get("/docs")
async def api_docs():
    """API documentation and usage examples."""
    return {
        "endpoints": {
            "GET /": "Health check",
            "GET /docs": "This API documentation",
            "POST /tools": "List all available CRM tools",
            "POST /messages": "Send a prompt to the CRM agent (with SSE streaming)",
            "POST /query": "Direct query endpoint (synchronous response)",
            "GET /sse": "Server-Sent Events stream for real-time responses"
        },
        "usage": {
            "POST /messages": {
                "url": "/messages?session_id={session_id}",
                "body": {
                    "prompt": "Your CRM query here",
                    "instance_url": "Your CRM instance URL",
                    "instance_api_key": "Your CRM instance API key"
                },
                "example": "Get me all contacts",
                "note": "Use with SSE endpoint for streaming responses"
            },
            "POST /query": {
                "url": "/query",
                "body": {
                    "prompt": "Your CRM query here",
                    "instance_url": "Your CRM instance URL",
                    "instance_api_key": "Your CRM instance API key"
                },
                "example": "Get me all contacts",
                "note": "Direct response, no streaming required"
            },
            "POST /tools": {
                "url": "/tools",
                "body": {
                    "instance_url": "Your CRM instance URL",
                    "instance_api_key": "Your CRM instance API key"
                },
                "note": "Returns list of available tools for the instance"
            }
        },
        "parameters": {
            "session_id": "Unique identifier for the conversation session",
            "instance_url": "Your CRM instance URL",
            "instance_api_key": "Your CRM instance API key"
        }
    }

# --- Tools Listing Endpoint (now accepts body with credentials) ---
@app.post("/tools")
async def list_tools(request: ToolsRequest):
    """List all available CRM tools for the given instance."""
    try:
        # Validate the instance credentials by trying to create tools
        crm_tools = CRMTools(request.instance_url, request.instance_api_key)
        
        return {
            "tools": [
                {
                    "name": "get_contacts",
                    "description": "Get all contacts from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_contact_relationships", 
                    "description": "Get contact relationships from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_contact_addresses",
                    "description": "Get contact addresses from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_companies",
                    "description": "Get all companies from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_company_relationships",
                    "description": "Get company relationships from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_company_addresses",
                    "description": "Get company addresses from the CRM module",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_system_fields",
                    "description": "Get system fields from the CRM system",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_contact_system_fields",
                    "description": "Get contact custom fields from the CRM system",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "get_company_system_fields",
                    "description": "Get company custom fields from the CRM system",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "save_contact",
                    "description": "Save or update a contact in the CRM system",
                    "inputSchema": {
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
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid instance credentials: {str(e)}")

@app.post("/query")
async def query_endpoint(request: QueryRequest):
    """Direct query endpoint (synchronous response)."""
    
    if not app.state.llm:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    try:
        # Create CRM tools with the provided credentials
        tools = create_crm_tools(request.instance_url, request.instance_api_key)
        
        # Create the agent with tools
        agent_executor = create_react_agent(app.state.llm, tools)
        
        # Process the query
        result = await agent_executor.ainvoke({
            "messages": [HumanMessage(content=request.prompt)]
        })
        
        # Extract the response
        response_content = result["messages"][-1].content if result.get("messages") else "No response generated"
        
        return {
            "response": response_content,
            "success": True
        }
        
    except Exception as e:
        print(f"Error in query endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "success": False
        }

@app.post("/messages")
async def messages_endpoint(
    request: MessageRequest,
    session_id: str
):
    """Send a prompt to the CRM agent (with SSE streaming)."""
    
    if not app.state.llm:
        raise HTTPException(status_code=500, detail="LLM not initialized")
    
    try:
        # Create CRM tools with the provided credentials
        tools = create_crm_tools(request.instance_url, request.instance_api_key)
        
        # Create the agent with tools
        agent_executor = create_react_agent(app.state.llm, tools)
        
        # Create a queue for this session if it doesn't exist
        if session_id not in message_queues:
            message_queues[session_id] = asyncio.Queue()
        
        # Process the query asynchronously and put result in queue
        async def process_query():
            try:
                result = await agent_executor.ainvoke({
                    "messages": [HumanMessage(content=request.prompt)]
                })
                
                response_content = result["messages"][-1].content if result.get("messages") else "No response generated"
                
                await message_queues[session_id].put({
                    "type": "response",
                    "content": response_content,
                    "session_id": session_id
                })
                
                # Signal end of stream
                await message_queues[session_id].put({"type": "end"})
                
            except Exception as e:
                await message_queues[session_id].put({
                    "type": "error",
                    "content": str(e),
                    "session_id": session_id
                })
        
        # Start processing in background
        asyncio.create_task(process_query())
        
        return {"status": "processing", "session_id": session_id}
        
    except Exception as e:
        print(f"Error in messages endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Message processing failed: {str(e)}")

@app.get("/sse")
async def sse_endpoint(session_id: str):
    """Server-Sent Events stream for real-time responses."""
    
    async def event_generator():
        try:
            if session_id not in message_queues:
                yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                return
            
            queue = message_queues[session_id]
            
            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if message["type"] == "end":
                        break
                    
                    yield f"data: {json.dumps(message)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keep-alive
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Clean up the queue
            if session_id in message_queues:
                del message_queues[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)