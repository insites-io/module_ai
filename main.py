import asyncio
import os
import uuid
import json
import uvicorn
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from collections import defaultdict
from typing import Dict, Any, Optional, List
import httpx
from pydantic import BaseModel
import logging

# Import tools directly
from servers.crm_tools import CRMTools
from servers.instance_tools import InstanceTools

# Configure logging for Cloud Run with proper formatting
# This should only be called once - other modules just use logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration to ensure Cloud Run picks it up
)
logger = logging.getLogger(__name__)

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration with graceful defaults for build-time ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION") 
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

CONSOLE_EMAIL = os.getenv("CONSOLE_EMAIL", "")

def setup_credentials():
    """
    Setup Google Cloud credentials.
    
    SECURITY NOTE: This function checks for credentials in this order:
    1. Cloud Run service account (production - automatic, no files needed)
    2. Local .env file (development only - NEVER commit credentials!)
    3. Explicit credentials file (development only - NEVER commit!)
    
    In production (Cloud Run), credentials are handled automatically via
    the service account assigned during deployment.
    """
    # Check if running on Cloud Run (production)
    if os.getenv("K_SERVICE"):  # K_SERVICE is set by Cloud Run
        logger.info("🔒 Running on Cloud Run - using built-in service account authentication")
        logger.info("✅ No credential files needed - automatic authentication enabled")
        return
    
    # Local development only
    logger.warning("⚠️  Running in local development mode")
    
    # Check for local credentials file (DEVELOPMENT ONLY!)
    credentials_path = os.path.join(os.path.dirname(__file__), "vertex-credentials.json")
    if os.path.exists(credentials_path):
        logger.warning("🚨 WARNING: Found vertex-credentials.json file!")
        logger.warning("🚨 This file should NEVER be committed to Git!")
        logger.warning("🚨 Using local credentials for development only")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        return
    
    # Check environment variable
    env_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_credentials:
        if os.path.exists(env_credentials):
            logger.warning(f"⚠️  Using credentials from environment: {env_credentials}")
            logger.warning("⚠️  Development mode only - do not commit credential files!")
        else:
            logger.error(f"❌ Credentials file not found: {env_credentials}")
    else:
        logger.info("ℹ️  No local credentials found - using default application credentials")
        logger.info("ℹ️  This is expected for Cloud Run deployments")

def validate_environment():
    """Validate environment variables when actually needed."""
    if not all([GCP_PROJECT_ID, GCP_REGION]):
        raise ValueError("GCP_PROJECT_ID and GCP_REGION must be set.")

# --- Asynchronous Message Queues for Streaming ---
message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

# ============================================================================
# PYDANTIC MODELS - MCP STANDARD
# ============================================================================

class QueryRequest(BaseModel):
    prompt: str
    instance_url: str
    instance_api_key: str

class MessageRequest(BaseModel):
    prompt: str
    instance_url: str
    instance_api_key: str

class ToolsRequest(BaseModel):
    """MCP standard tools/list request"""
    instance_url: str
    instance_api_key: str

class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class ToolsListResponse(BaseModel):
    tools: List[Tool]

class CallToolRequest(BaseModel):
    name: str
    arguments: Optional[Dict[str, Any]] = None

class CallToolResponse(BaseModel):
    content: List[Dict[str, Any]]
    isError: Optional[bool] = False

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting MCP CRM Server...")
    
    setup_credentials()
    # Validate environment at startup (runtime)
    try:
        validate_environment()
    except ValueError as e:
        logger.error(f"❌ Environment validation failed: {e}")
        app.state.llm = None
        yield
        return
    
    # Initialize LLM
    try:
        logger.info("🔧 Initializing LLM...")
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            temperature=0,
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
        )
        app.state.llm = llm
        logger.info("✅ LLM initialized successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing LLM: {e}")
        import traceback
        traceback.print_exc()
        app.state.llm = None
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down MCP CRM Server...")

app = FastAPI(
    title="MCP CRM API",
    description="API for CRM operations using MCP standard protocol",
    version="2.0.0",
    lifespan=lifespan
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_crm_tools(instance_url: str, instance_api_key: str):
    """Create CRM tools with the given instance credentials."""
    crm_tools = CRMTools(instance_url, instance_api_key)
    return crm_tools.get_langchain_tools()

# ============================================================================
# MCP STANDARD ENDPOINTS
# ============================================================================

@app.post("/mcp/tools/list")
async def mcp_list_tools(request: ToolsRequest) -> ToolsListResponse:
    """
    MCP standard endpoint: List all available tools.
    This follows the MCP protocol specification.
    """
    try:
        # Validate the instance credentials
        crm_tools = CRMTools(request.instance_url, request.instance_api_key)

    
        return ToolsListResponse(
            tools=[
                # ========== CONTACT TOOLS ==========
                Tool(
                    name="get_contacts",
                    description="Retrieves contacts from the CRM with pagination, sorting, and search. Returns a list of contact objects with id, email, first_name, last_name, and custom properties.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "Page number for pagination (default: 1)"
                            },
                            "size": {
                                "type": "integer",
                                "description": "Number of contacts per page (default: 10)"
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "Field to sort by (e.g., 'last_name', 'first_name', 'email')"
                            },
                            "search_by": {
                                "type": "string",
                                "description": "Field to search in (e.g., 'first_name', 'last_name', 'email')"
                            },
                            "keyword": {
                                "type": "string",
                                "description": "Search keyword to filter contacts"
                            },
                            "sort_order": {
                                "type": "string",
                                "description": "Sort order: 'ASC' or 'DESC' (default: 'ASC')",
                                "enum": ["ASC", "DESC"]
                            }
                        }
                    }
                ),
                Tool(
                    name="create_contact",
                    description="Creates a new contact in the Insites CRM. Requires an email address at minimum. Use the 'properties' field to store additional details like phone numbers, job titles, or company names. If email already exists, this will fail - you should then search for the contact and use update_contact instead.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "The email address of the new contact. Must be unique (required)."
                            },
                            "first_name": {
                                "type": "string",
                                "description": "The contact's first name"
                            },
                            "last_name": {
                                "type": "string",
                                "description": "The contact's last name"
                            },
                        },
                        "required": ["email"]
                    }
                ),
                Tool(
                    name="update_contact",
                    description="Updates the details of an existing contact in the Insites CRM. You must provide the contact's unique 'uuid'. If you only have an email, use 'get_contacts' with search first to retrieve the 'uuid'. Only fields you provide will be updated - others remain unchanged.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "uuid": {
                                "type": "string",
                                "description": "The unique UUID of the contact to update (required)"
                            },
                            "email": {
                                "type": "string",
                                "description": "New email address (optional, only if changing it)"
                            },
                            "first_name": {
                                "type": "string",
                                "description": "Updated first name (optional)"
                            },
                            "last_name": {
                                "type": "string",
                                "description": "Updated last name (optional)"
                            },
                        },
                        "required": ["uuid"]
                    }
                ),

                # ========== COMPANY TOOLS ==========
                Tool(
                    name="get_companies",
                    description="Retrieves companies from the CRM with pagination, sorting, and search. Returns a list of company objects with uuid, company_name, and other details.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "Page number for pagination (default: 1)"
                            },
                            "size": {
                                "type": "integer",
                                "description": "Number of companies per page (default: 10)"
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "Field to sort by (e.g., 'company_name', 'created_at')"
                            },
                            "search_by": {
                                "type": "string",
                                "description": "Field to search in (e.g., 'company_name')"
                            },
                            "keyword": {
                                "type": "string",
                                "description": "Search keyword to filter companies"
                            },
                            "sort_order": {
                                "type": "string",
                                "description": "Sort order: 'ASC' or 'DESC' (default: 'ASC')",
                                "enum": ["ASC", "DESC"]
                            }
                        }
                    }
                ),
                Tool(
                    name="create_company",
                    description="Creates a new company in the Insites CRM. Requires company_name at minimum. Supports comprehensive company data including contact details, social links, tax info, and custom fields.",
                    inputSchema={
                        "type": "object",
                        "properties":{
                            "company_name":{
                                "type":"string",
                                "description":"The name of the company (required)"
                            },
                            "registered_business_number":{
                                "type":"string",
                                "description":"Official business registration number"
                            },
                            "website":{
                                "type":"string",
                                "description":"Company website URL"
                            },
                            "email_1":{
                                "type":"string",
                                "description":"Primary email address"
                            },
                            "email_2":{
                                "type":"string",
                                "description":"Secondary email address"
                            },
                            "email_3":{
                                "type":"string",
                                "description":"Tertiary email address"
                            },
                            "phone_1_country_code":{
                                "type":"string",
                                "description":"Country code for primary phone (e.g., '1' for US)"
                            },
                            "phone_1_number":{
                                "type":"string",
                                "description":"Primary phone number"
                            },
                            "phone_2_country_code":{
                                "type":"string",
                                "description":"Country code for secondary phone"
                            },
                            "phone_2_number":{
                                "type":"string",
                                "description":"Secondary phone number"
                            },
                            "phone_3_country_code":{
                                "type":"string",
                                "description":"Country code for tertiary phone"
                            },
                            "phone_3_number":{
                                "type":"string",
                                "description":"Tertiary phone number"
                            },
                            "mobile_phone_country_code":{
                                "type":"string",
                                "description":"Country code for mobile phone"
                            },
                            "mobile_phone_number":{
                                "type":"string",
                                "description":"Mobile phone number"
                            }
                        },
                        "required": ["company_name"],
                        "additionalProperties": True
                    }
                ),
                Tool(
                    name="update_company",
                    description="Updates an existing company in the Insites CRM. You must provide the company's unique 'uuid'. Only fields you provide will be updated - others remain unchanged.",
                    inputSchema={
                        "type": "object",
                        "properties":{
                            "uuid":{
                                "type":"string",
                                "description":"The unique UUID of the company to update (required)"
                            },
                            "company_name":{
                                "type":"string",
                                "description":"Updated company name"
                            },
                            "registered_business_number":{
                                "type":"string",
                                "description":"Updated business registration number"
                            },
                            "website":{
                                "type":"string",
                                "description":"Updated website URL"
                            },
                            "email_1":{
                                "type":"string",
                                "description":"Updated primary email"
                            },
                            "email_2":{
                                "type":"string",
                                "description":"Updated secondary email"
                            },
                            "email_3":{
                                "type":"string",
                                "description":"Updated tertiary email"
                            },
                            "phone_1_country_code":{
                                "type":"string",
                                "description":"Updated country code for primary phone"
                            },
                            "phone_1_number":{
                                "type":"string",
                                "description":"Updated primary phone number"
                            },
                            "phone_2_country_code":{
                                "type":"string",
                                "description":"Updated country code for secondary phone"
                            },
                            "phone_2_number":{
                                "type":"string",
                                "description":"Updated secondary phone number"
                            },
                            "phone_3_country_code":{
                                "type":"string",
                                "description":"Updated country code for tertiary phone"
                            },
                            "phone_3_number":{
                                "type":"string",
                                "description":"Updated tertiary phone number"
                            },
                            "mobile_phone_country_code":{
                                "type":"string",
                                "description":"Updated mobile country code"
                            },
                            "mobile_phone_number":{
                                "type":"string",
                                "description":"Updated mobile phone number"
                            }
                        },
                        "required": ["uuid"],
                        "additionalProperties": True
                    }
                ),
                
                # # ========== OTHER TOOLS ==========
                # Tool(
                #     name="get_contact_relationships",
                #     description="Get contact relationships from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_contact_addresses",
                #     description="Get contact addresses from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_company_relationships",
                #     description="Get company relationships from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_company_addresses",
                #     description="Get company addresses from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_system_fields",
                #     description="Get system fields from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_contact_system_fields",
                #     description="Get contact custom fields from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # ),
                # Tool(
                #     name="get_company_system_fields",
                #     description="Get company custom fields from the CRM system",
                #     inputSchema={"type": "object", "properties": {}}
                # )
                # ========== INSTANCE MANAGEMENT TOOLS ==========
                Tool(
                    name="validate_subdomain",
                    description="Validate if a name is available for a new Insites instance before creating it.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name to check (e.g., 'my-new-site')"
                            }
                        },
                        "required": ["name"]
                    }
                ),
                # Tool(
                #     name="create_instance",
                #     description="Create a new PlatformOS instance. This tool automatically validates subdomain availability before creating the instance. Requires subdomain, pos_billing_plan_id, and pos_data_centre_id.",
                #     inputSchema={
                #         "type": "object",
                #         "properties": {
                #             "subdomain": {
                #                 "type": "string",
                #                 "description": "The subdomain for the new instance (required)"
                #             },
                #             "pos_billing_plan_id": {
                #                 "type": "string",
                #                 "description": "POS billing plan ID (required)"
                #             },
                #             "pos_data_centre_id": {
                #                 "type": "string",
                #                 "description": "POS data centre ID (required)"
                #             },
                #             "tags": {
                #                 "type": "array",
                #                 "items": {"type": "string"},
                #                 "description": "List of tags for the instance (optional)"
                #             },
                #             "created_by": {
                #                 "type": "string",
                #                 "description": "Email or ID of user creating the instance (optional)"
                #             },
                #             "is_duplication": {
                #                 "type": "boolean",
                #                 "description": "Whether this is a duplication (default: false)"
                #             },
                #             "environment": {
                #                 "type": "string",
                #                 "description": "Environment: 'staging' or 'production' (default: 'production')",
                #                 "enum": ["staging", "production"]
                #             }
                #         },
                #         "required": ["subdomain", "pos_billing_plan_id", "pos_data_centre_id"]
                #     }
                # ),
                Tool(
                    name="create_instance",
                    description="""Complete Insites instance creation workflow (RECOMMENDED). 
                    
                    IMPORTANT: When presenting results to the user, always use the phrase "Insites instance" in your response.
                    
                    This tool performs a 3-step process:
                    1. Validates subdomain availability
                    2. Creates Insites instance record in Console database (CRUCIAL)
                    3. Sets up AWS Gateway configuration
                    
                    Returns structured information including:
                    - Instance name and subdomain
                    - Full URL (with environment)
                    - Current status
                    - Environment (staging/production)
                    
                    When presenting results, format your response like:
                    "Perfect! I've successfully created your new Insites instance '[name]'. Here are the details:"
                    Then show the instance details clearly.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string", 
                                "description": "Instance name/subdomain (required)"
                            },
                            "environment": {
                                "type": "string",
                                "description": "Environment: 'staging' or 'production' (default: 'staging')",
                                "enum": ["staging", "production"]
                            }
                        },
                        "required": ["name"]
                    }
                )
            ]
        )
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Full traceback: {error_traceback}")
        raise HTTPException(status_code=400, detail=f"Error listing tools: {str(e)}\n\nTraceback:\n{error_traceback}")

@app.post("/mcp/tools/call")
async def mcp_call_tool(request: CallToolRequest, instance_url: Optional[str] = None, instance_api_key: Optional[str] = None) -> CallToolResponse:
    """
    MCP standard endpoint: Execute a tool with given arguments.
    Note: instance_url and instance_api_key are required for CRM tools, optional for instance management tools
    """
    try:        
        # Route to appropriate tool handler based on tool name
        tool_name = request.name
        args = request.arguments or {}
        
        logger.info(f"📥 Tool call received: name='{tool_name}', args keys={list(args.keys())}, instance_url={bool(instance_url)}, instance_api_key={bool(instance_api_key)}")
        # CRM Tools
        if tool_name in ["get_contacts", "create_contact", "update_contact", 
                         "get_companies", "create_company", "update_company"]:
            if not instance_url or not instance_api_key:
                return CallToolResponse(
                    content=[{
                        "type": "text",
                        "text": "instance_url and instance_api_key query parameters are required for CRM tools"
                    }],
                    isError=True
                )
            crm = CRMTools(instance_url, instance_api_key)
            # ... existing CRM tool handlers ...
        
            # Execute the appropriate method
            if tool_name == "get_contacts":
                result = crm.get_contacts(args)
            # elif tool_name == "get_contact_relationships":
            #     result = crm.get_contact_relationships()
            # elif tool_name == "get_contact_addresses":
            #     result = crm.get_contact_addresses()
            elif tool_name == "get_companies":
                result = crm.get_companies(args)
            # elif tool_name == "get_company_relationships":
            #     result = crm.get_company_relationships()
            # elif tool_name == "get_company_addresses":
            #     result = crm.get_company_addresses()
            # elif tool_name == "get_system_fields":
            #     result = crm.get_system_fields()
            # elif tool_name == "get_contact_system_fields":
            #     result = crm.get_contact_system_fields()
            # elif tool_name == "get_company_system_fields":
            #     result = crm.get_company_system_fields()
            # elif tool_name == "save_contact":
            #     result = crm.save_contact(args.get("contact_data", {}))
            elif tool_name == "create_contact":
                result = crm.save_contact(args)  # Create is same as save without uuid
            elif tool_name == "update_contact":
                result = crm.save_contact(args)  # Update is save with uuid
            elif tool_name == "create_company":
                result = crm.create_company(args) 
            elif tool_name == "update_company":
                result = crm.update_company(args) 
            else:
                return CallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"Unknown tool: {tool_name}"
                    }],
                    isError=True
                )
        # Instance Management Tools
        elif tool_name in ["validate_subdomain", "create_instance"]:
            logger.info(f"🔧 Processing instance tool: {tool_name}")
            
            # Ensure GCP_PROJECT_ID is set (required for Secret Manager)
            if not GCP_PROJECT_ID:
                return CallToolResponse(
                    content=[{
                        "type": "text",
                        "text": "GCP_PROJECT_ID environment variable is not set. This is required for Secret Manager access."
                    }],
                    isError=True
                )
            
            # Get Console credentials
            console_email = args.pop("console_email", None) or os.getenv("CONSOLE_EMAIL", "")
            
            if not console_email and tool_name == "create_instance":
                logger.warning("⚠️  CONSOLE_EMAIL not provided, some operations may fail")
            
            # Initialize instance tools - it will fetch credentials from Secret Manager internally
            try:
                instance_tools = InstanceTools(
                    console_email=console_email
                )
                logger.info("✅ InstanceTools initialized successfully")
            except Exception as init_error:
                logger.error(f"❌ Failed to initialize InstanceTools: {init_error}")
                import traceback
                traceback.print_exc()
                return CallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"Failed to initialize InstanceTools: {str(init_error)}\n\nThis usually means:\n1. GCP_PROJECT_ID is not set\n2. Secret Manager permissions are missing\n3. Required secrets don't exist in Secret Manager\n\nTraceback:\n{traceback.format_exc()}"
                    }],
                    isError=True
                )
            
            # Execute instance tool
            result = None
            try:
                if tool_name == "validate_subdomain":
                    # Handle both "name" and "subdomain" parameter names for compatibility
                    subdomain_input = args.get("name") or args.get("subdomain", "")
                    if not subdomain_input:
                        return CallToolResponse(
                            content=[{
                                "type": "text",
                                "text": "Missing required parameter: 'name' or 'subdomain' is required for validate_subdomain"
                            }],
                            isError=True
                        )
                    logger.info(f"🔍 Validating subdomain: {subdomain_input}")
                    result = instance_tools.validate_subdomain(name=subdomain_input)
                
                elif tool_name == "create_instance":
                    # Validate required parameters
                    name = args.get("name")
                    if not name:
                        return CallToolResponse(
                            content=[{
                                "type": "text",
                                "text": "Missing required parameter: 'name' is required for create_instance"
                            }],
                            isError=True
                        )
                    
                    # Provide default for environment if not specified
                    environment = args.get("environment", "production")
                    
                    logger.info(f"🚀 Creating instance: name={name}, environment={environment}")
                    result = instance_tools.create_instance_complete_workflow(
                        name=name,
                        environment=environment
                    )
                else:
                    return CallToolResponse(
                        content=[{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                        isError=True
                    )
            except Exception as tool_error:
                logger.error(f"❌ Error executing instance tool '{tool_name}': {tool_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return CallToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"Failed to execute tool '{tool_name}': {str(tool_error)}\n\nTraceback:\n{traceback.format_exc()}"
                    }],
                    isError=True
                )
        
        # Check if result exists
        if result is None:
            logger.error(f"❌ Tool '{tool_name}' returned None result")
            return CallToolResponse(
                content=[{
                    "type": "text",
                    "text": f"Tool execution returned no result for: {tool_name}"
                }],
                isError=True
            )
        
        if tool_name == "create_instance" and result.get("success"):
            instance = result.get("instance", {})
            name = instance.get("name", "")
            url = instance.get("url", "")
            environment = instance.get("environment", "")
            status = instance.get("status", "Initializing")
            
            formatted_response = {
                "status": "success",
                "summary": f"Perfect! I've successfully created your new Insites instance '{name}'.",
                "instance_type": "Insites Instance",
                "details": {
                    "Instance Name": name,
                    "URL": url,
                    "Status": status,
                    "Environment": environment.capitalize()
                },
                "additional_info": "The Insites instance has been created in the database and the AWS Gateway setup has been initiated. The instance is currently initializing and should be ready to use shortly."
            }
            return CallToolResponse(
                content=[{
                    "type": "text",
                    "text": formatted_response
                }],
                isError=False
            )
        # Check if result indicates an error
        is_error = not result.get("success", True)
        
        logger.info(f"✅ Tool '{tool_name}' executed. Success: {not is_error}")
        if is_error:
            logger.warning(f"⚠️  Tool '{tool_name}' returned error: {result.get('error', 'Unknown error')}")
        
        return CallToolResponse(
            content=[{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }],
            isError=is_error
        )
        
    except Exception as e:
        logger.error(f"Error executing tool '{request.name}': {e}")
        import traceback
        error_detail = f"Error executing tool '{request.name}': {str(e)}\n{traceback.format_exc()}"
        return CallToolResponse(
            content=[{
                "type": "text",
                "text": error_detail
            }],
            isError=True
        )

# ============================================================================
# LEGACY ENDPOINTS (for backward compatibility)
# ============================================================================

@app.get("/")
async def health_check():
    """Health check endpoint for the API service."""
    return {
        "status": "healthy",
        "service": "Insites MCP Sever",
        "version": "0.1.2",
        "message": "Server is running and ready",
    }

# Legacy /tools endpoint for backward compatibility
@app.post("/tools")
async def list_tools(request: ToolsRequest):
    """Legacy endpoint - redirects to MCP standard."""
    return await mcp_list_tools(request)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)