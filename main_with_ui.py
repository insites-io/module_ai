# --- File: main_with_ui.py (The MCP Server/API with UI) ---
# This is a FastAPI server that acts as the MCP server and serves a web UI.
# It receives prompts, processes them using a LangChain agent, and streams the response.

import asyncio
import os
import uuid
import json
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
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

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration ---
# --- IMPORTANT: These environment variables MUST be set in your Cloud Run service or .env file ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")

# Handle credentials - use environment variable if set, otherwise use local credentials file
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./vertex-credentials.json")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH
print(f"Using credentials from: {CREDENTIALS_PATH}")

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
    print(f"📋 Project ID: {GCP_PROJECT_ID}")
    print(f"🌍 Region: {GCP_REGION}")
    print(f"🤖 Model: {GEMINI_MODEL_NAME}")
    
    try:
        print("🔧 Initializing LLM and MCP tools...")
        # Initialize the LLM (Claude on Vertex AI)
        llm = ChatVertexAI(
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
            model_name=GEMINI_MODEL_NAME,
            temperature=0,
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

# --- Initialize the LLM and Tools once per server start (for performance) ---
# We use a global variable to store the initialized agent and tools
# This is a common pattern in serverless containers for warm starts

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
            "POST /messages": "Send a prompt to the CRM agent (with SSE streaming)",
            "POST /query": "Direct query endpoint (synchronous response)",
            "GET /sse": "Server-Sent Events stream for real-time responses"
        },
        "usage": {
            "GET /ui": {
                "description": "Access the web interface for the CRM assistant",
                "note": "Open this URL in your browser to use the UI"
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
        "parameters": {
            "session_id": "Unique identifier for the conversation session",
            "instance_url": "Your CRM instance URL",
            "instance_api_key": "Your CRM instance API key"
        }
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

    # Start the agent's work in a separate task so the POST request can return quickly
    async def run_agent():
        response_text = ""
        try:
            # Check if LLM is available
            if not hasattr(app.state, 'llm') or app.state.llm is None:
                response_text = "Error: LLM not initialized. Please check server logs."
                return
                
            # Create server parameters with instance variables as command line arguments
            server_args = ["servers/crm_server.py"]
            if instance_url:
                server_args.extend(["--instance-url", instance_url])
            if instance_api_key:
                server_args.extend(["--instance-api-key", instance_api_key])
            
            print(f"DEBUG: Starting MCP server with args: {server_args}")
            
            stdio_server_params = StdioServerParameters(
                command="python",
                args=server_args,
            )
            
            print(f"DEBUG: About to start stdio client")
            
            # Create a new MCP session for this request
            async with stdio_client(stdio_server_params) as (read, write):
                print(f"DEBUG: stdio client started")
                async with ClientSession(read_stream=read, write_stream=write) as session:
                    print(f"DEBUG: ClientSession created")
                    await session.initialize()
                    print(f"DEBUG: Session initialized")
                    tools = await load_mcp_tools(session)
                    print(f"DEBUG: Loaded {len(tools)} tools")
                    
                    # Create agent with tools for this request
                    agent = create_react_agent(app.state.llm, tools)
                    
                    # ainvoke returns a dictionary
                    result = await agent.ainvoke(
                        {"messages": [HumanMessage(content=prompt)]}
                    )
                    response_text = result["messages"][-1].content
        except Exception as e:
            import traceback
            print(f"DEBUG: Error occurred: {e}")
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            response_text = f"An error occurred: {e}"
        finally:
            try:
                # Once the agent is done, put the final message and a stop signal in the queue
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
        server_args = ["servers/crm_server.py"]
        if instance_url:
            server_args.extend(["--instance-url", instance_url])
        if instance_api_key:
            server_args.extend(["--instance-api-key", instance_api_key])
        
        stdio_server_params = StdioServerParameters(
            command="python",
            args=server_args,
        )
        
        # Create a new MCP session for this request
        async with stdio_client(stdio_server_params) as (read, write):
            async with ClientSession(read_stream=read, write_stream=write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                
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

        while True:
            try:
                message = await message_queues[session_id].get()
                if message == "END_STREAM":
                    break
                yield f"data: {message}\n\n"
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

