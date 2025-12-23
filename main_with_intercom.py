"""
MCP Protocol Adapter for CRM Server
Add this to your existing main.py or create as a separate file and import
"""

import json
import hashlib
from typing import Optional, Dict, Any, List, Union
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from servers.crm_tools import CRMTools
from fastapi.middleware.cors import CORSMiddleware

# --- FastAPI App ---
app = FastAPI(
    title="MCP CRM API for Intercom",
    description="MCP protocol endpoint for CRM operations via Intercom integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins including Intercom
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# --- Environment Variables for Security ---
INTERCOM_API_KEY = "dG9rOjg0NzFlYmM0X2IyZmRfNDljN19iYmYwXzBjZjZlN2UzZTNmZDoxOjA="  # Set this in your .env
MCP_INSTANCE_URL = "https://iia-eric-v2.staging.oregon.platform-os.com"  # Your default CRM instance URL
MCP_INSTANCE_API_KEY = "instance_6153cf7d-0f2c-47cf-a71a-69e308ff08b3_PEpn2gnKf1BVeVHmeJfIufnsiam72sl_s5LsfoxmnFQ"  # Your default CRM API key


# --- MCP Protocol Models ---
class MCPToolInputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = {}
    required: List[str] = []

class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: MCPToolInputSchema

class MCPTextContent(BaseModel):
    type: str = "text"
    text: str

class MCPToolResponse(BaseModel):
    content: List[MCPTextContent]
    isError: Optional[bool] = False

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[int, str]] = None
    
    class Config:
        extra = "allow"  # Allow extra fields from Intercom

class MCPError(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None

# --- Authentication Middleware ---
async def verify_intercom_auth(authorization: Optional[str] = Header(None)):
    """Verify authentication from Intercom or other clients"""
    if not INTERCOM_API_KEY:
        # If no API key is set, allow all requests (dev mode)
        print("⚠️ Warning: INTERCOM_API_KEY not set - authentication disabled")
        return True
    
    if not authorization:
        print("⚠️ No authorization header provided")
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # Extract bearer token - handle different formats
    token = authorization.strip()
    if token.startswith("Bearer "):
        token = token[7:]  # Remove "Bearer " prefix
    elif token.startswith("bearer "):
        token = token[7:]  # Handle lowercase
    
    print(f"🔐 Auth attempt - token hash: {hashlib.sha256(token.encode()).hexdigest()[:8]}")
    
    if token != INTERCOM_API_KEY:
        print("❌ Invalid API key provided")
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    print("✅ Authentication successful")
    return True

# --- MCP Tool Definitions ---
def get_mcp_tools() -> List[MCPTool]:
    """Define all available MCP tools"""
    return [
        MCPTool(
            name="get_contacts",
            description="Retrieve all contacts from the CRM system. Returns a list of contact records with their details.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_contact_relationships",
            description="Get relationships between contacts (e.g., family members, colleagues, references).",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_contact_addresses",
            description="Retrieve all addresses associated with contacts in the CRM.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_companies",
            description="Retrieve all companies from the CRM system. Returns a list of company records.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_company_relationships",
            description="Get relationships between companies (e.g., parent companies, subsidiaries, partners).",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_company_addresses",
            description="Retrieve all addresses associated with companies in the CRM.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_system_fields",
            description="Get all system-defined fields and their metadata from the CRM.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_contact_system_fields",
            description="Get custom field definitions for contacts in the CRM system.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="get_company_system_fields",
            description="Get custom field definitions for companies in the CRM system.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={},
                required=[]
            )
        ),
        MCPTool(
            name="save_contact",
            description="Create a new contact or update an existing contact in the CRM system. Provide contact data as a JSON object.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={
                    "contact_data": {
                        "type": "object",
                        "description": "Contact data to save (e.g., {\"first_name\": \"John\", \"last_name\": \"Doe\", \"email\": \"john@example.com\"})"
                    }
                },
                required=["contact_data"]
            )
        ),
        MCPTool(
            name="search_contacts",
            description="Search for contacts by name, email, or other criteria. Returns matching contact records.",
            inputSchema=MCPToolInputSchema(
                type="object",
                properties={
                    "query": {
                        "type": "string",
                        "description": "Search query (name, email, phone, etc.)"
                    }
                },
                required=["query"]
            )
        ),
    ]

# --- MCP Tool Execution ---
async def execute_mcp_tool(name: str, arguments: Dict[str, Any]) -> MCPToolResponse:
    """Execute a CRM tool and return MCP-formatted response"""
    
    try:
        # Initialize CRM tools with default credentials
        if not MCP_INSTANCE_URL or not MCP_INSTANCE_API_KEY:
            raise ValueError("MCP_INSTANCE_URL and MCP_INSTANCE_API_KEY must be set in environment")
        
        crm_tools = CRMTools(MCP_INSTANCE_URL, MCP_INSTANCE_API_KEY)
        
        # Route to appropriate tool
        if name == "get_contacts":
            result = crm_tools.get_contacts()
            
        elif name == "get_contact_relationships":
            result = crm_tools.get_contact_relationships()
            
        elif name == "get_contact_addresses":
            result = crm_tools.get_contact_addresses()
            
        elif name == "get_companies":
            result = crm_tools.get_companies()
            
        elif name == "get_company_relationships":
            result = crm_tools.get_company_relationships()
            
        elif name == "get_company_addresses":
            result = crm_tools.get_company_addresses()
            
        elif name == "get_system_fields":
            result = crm_tools.get_system_fields()
            
        elif name == "get_contact_system_fields":
            result = crm_tools.get_contact_system_fields()
            
        elif name == "get_company_system_fields":
            result = crm_tools.get_company_system_fields()
            
        elif name == "save_contact":
            contact_data = arguments.get("contact_data")
            if not contact_data:
                raise ValueError("contact_data is required")
            result = crm_tools.save_contact(contact_data)
            
        elif name == "search_contacts":
            query = arguments.get("query")
            if not query:
                raise ValueError("query parameter is required")
            # Implement search logic
            all_contacts = crm_tools.get_contacts()
            result = [
                contact for contact in all_contacts
                if query.lower() in json.dumps(contact).lower()
            ]
            
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        # Format result as MCP response
        return MCPToolResponse(
            content=[
                MCPTextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )
            ],
            isError=False
        )
        
    except Exception as e:
        # Return error in MCP format
        return MCPToolResponse(
            content=[
                MCPTextContent(
                    type="text",
                    text=f"Error executing tool '{name}': {str(e)}"
                )
            ],
            isError=True
        )

# --- MCP Endpoint ---
@app.options("/mcp")
async def mcp_options():
    """Handle CORS preflight requests"""
    return {
        "status": "ok"
    }

@app.post("/mcp", dependencies=[Depends(verify_intercom_auth)])
async def mcp_endpoint(request: Request) -> MCPResponse:
    """
    MCP protocol endpoint for Intercom integration.
    Handles tools/list and tools/call methods.
    """
    
    # Parse request body manually for better error handling
    request_id = None
    try:
        body = await request.body()
        body_str = body.decode()
        print(f"📥 Raw MCP Request Body: {body_str}")
        
        request_data = json.loads(body_str)
        request_id = request_data.get('id')  # Extract ID before validation
        print(f"📋 Parsed MCP Request: method={request_data.get('method')}, id={request_id}")
        
        mcp_request = MCPRequest(**request_data)
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        # Try to extract ID from raw body if JSON parsing partially worked
        if 'request_data' in locals():
            request_id = request_data.get('id')
        return MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            error=MCPError(
                code=-32700,
                message=f"Parse error: {str(e)}"
            )
        )
    except Exception as e:
        print(f"❌ Request parsing error: {e}")
        return MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            error=MCPError(
                code=-32600,
                message=f"Invalid Request: {str(e)}"
            )
        )
    
    print(f"📥 MCP Request: method={mcp_request.method}, id={mcp_request.id}")
    
    try:
        # Handle tools/list method
        if mcp_request.method == "tools/list":
            tools = get_mcp_tools()
            return MCPResponse(
                jsonrpc="2.0",
                id=mcp_request.id or 1,
                result={
                    "tools": [tool.dict() for tool in tools]
                }
            )
        
        # Handle tools/call method
        elif mcp_request.method == "tools/call":
            params = mcp_request.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return MCPResponse(
                    jsonrpc="2.0",
                    id=mcp_request.id or 1,
                    error=MCPError(
                        code=-32602,
                        message="Missing 'name' parameter"
                    )
                )
            
            # Execute the tool
            tool_response = await execute_mcp_tool(tool_name, arguments)
            
            return MCPResponse(
                jsonrpc="2.0",
                id=mcp_request.id or 1,
                result=tool_response.dict()
            )
        
        # Handle initialize method (optional but recommended)
        elif mcp_request.method == "initialize":
            return MCPResponse(
                jsonrpc="2.0",
                id=mcp_request.id or 1,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "CRM MCP Server",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            )
        
        # Unknown method
        else:
            return MCPResponse(
                jsonrpc="2.0",
                id=mcp_request.id or 1,
                error=MCPError(
                    code=-32601,
                    message=f"Method not found: {mcp_request.method}"
                )
            )
            
    except Exception as e:
        print(f"Error in MCP endpoint: {e}")
        import traceback
        traceback.print_exc()
        
        return MCPResponse(
            jsonrpc="2.0",
            id=mcp_request.id if 'mcp_request' in locals() else request_id,
            error=MCPError(
                code=-32000,
                message=f"Server error: {str(e)}"
            )
        )

# --- MCP Health Check ---
@app.get("/mcp/health")
async def mcp_health_check():
    """Health check specifically for MCP endpoint"""
    return {
        "status": "healthy",
        "protocol": "MCP",
        "version": "2024-11-05",
        "authenticated": bool(INTERCOM_API_KEY),
        "crm_configured": bool(MCP_INSTANCE_URL and MCP_INSTANCE_API_KEY)
    }