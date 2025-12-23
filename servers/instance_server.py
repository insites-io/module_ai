import asyncio
import argparse
import sys
import os
import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
import json

from servers.instance_tools import InstanceTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Argument Parsing
def parse_arguments():
    parser = argparse.ArgumentParser(description='MCP Instance Management Server')
    parser.add_argument('--aws-create-instance-url', type=str, required=True, 
                       help='AWS Create Instance Base URL')
    parser.add_argument('--aws-instance-jwt-secret', type=str, required=True, 
                       help='AWS Instance JWT secret for authentication')
    return parser.parse_args()

# Parse arguments
try:
    args = parse_arguments()
    AWS_CREATE_INSTANCE_URL = args.aws_create_instance_url
    AWS_JWT_SECRET = args.aws_instance_jwt_secret
except SystemExit as e:
    if "--help" in sys.argv or "--version" in sys.argv:
        sys.exit(e.code)
    AWS_CREATE_INSTANCE_URL = os.getenv("AWS_CREATE_INSTANCE_URL")
    AWS_INSTANCE_JWT_SECRET = os.getenv("AWS_INSTANCE_JWT_SECRET")

# FastMCP Initialization
_mcp_instance = None

def get_mcp():
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = FastMCP("instance-server")
    return _mcp_instance

class MCPProxy:
    def tool(self, *args, **kwargs):
        return get_mcp().tool(*args, **kwargs)
    
    def run(self, *args, **kwargs):
        return get_mcp().run(*args, **kwargs)

mcp = MCPProxy()

# MCP Tools
@mcp.tool()
def validate_subdomain(subdomain: str) -> Dict[str, Any]:
    """
    Validate if a subdomain is available for a new PlatformOS instance.
    
    Args:
        subdomain: The subdomain to check (e.g., 'my-new-site')
    
    Returns:
        Dict[str, Any]: Validation result indicating if subdomain is available
    """
    logger.info(f"Validating subdomain: {subdomain}")
    
    if not AWS_CREATE_INSTANCE_URL or not AWS_INSTANCE_JWT_SECRET:
        return {
            "success": False,
            "error": "AWS API Gateway URL and JWT secret not configured"
        }
    
    instance_tools = InstanceTools(AWS_CREATE_INSTANCE_URL, AWS_JWT_SECRET)
    result = instance_tools.validate_subdomain(subdomain)
    logger.info(f"Subdomain validation result: {result}")
    return result

@mcp.tool()
def create_instance(instance_data: Dict[str, Any], environment: str = "production") -> Dict[str, Any]:
    """
    Create a new PlatformOS instance. Automatically validates subdomain availability first.
    
    Args:
        instance_data: Dictionary containing:
            - subdomain: The subdomain for the instance (required)
            - pos_billing_plan_id: POS billing plan ID (required)
            - pos_data_centre_id: POS data centre ID (required)
            - tags: List of tags (optional)
            - created_by: User who created the instance (optional)
            - is_duplication: Whether this is a duplication (optional)
        environment: 'staging' or 'production' (default: 'production')
    
    Returns:
        Dict[str, Any]: Creation result with instance details or error information
    """
    logger.info(f"Creating instance with data: {instance_data}")
    
    if not AWS_CREATE_INSTANCE_URL or not AWS_INSTANCE_JWT_SECRET:
        return {
            "success": False,
            "error": "AWS API Gateway URL and JWT secret not configured"
        }
    
    instance_tools = InstanceTools(AWS_CREATE_INSTANCE_URL, AWS_INSTANCE_JWT_SECRET)
    result = instance_tools.create_instance(instance_data, environment)
    logger.info(f"Instance creation result: {result}")
    return result

# Entry Point
if __name__ == "__main__":
    logger.info("Starting MCP Instance Management Server...")
    logger.info(f"AWS_CREATE_INSTANCE_URL: {AWS_CREATE_INSTANCE_URL}")
    logger.info(f"AWS_INSTANCE_JWT_SECRET: {'*' * 10 if AWS_INSTANCE_JWT_SECRET else 'None'}")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Error in mcp.run: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")