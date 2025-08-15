#!/usr/bin/env python3
"""
Tool Discovery Script for MCP CRM Server

This script demonstrates how to discover and list all available tools
from an MCP server without needing the full FastAPI application.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path to import from servers
sys.path.append(str(Path(__file__).parent))

async def discover_tools():
    """Discover and list all available MCP tools."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from langchain_mcp_adapters.tools import load_mcp_tools
        
        print("🔍 Discovering MCP tools...")
        
        # Get the path to the CRM server script
        crm_server_path = Path(__file__).parent / "servers" / "crm_server.py"
        
        if not crm_server_path.exists():
            print(f"❌ CRM server not found at: {crm_server_path}")
            return
        
        print(f"📁 Using CRM server at: {crm_server_path}")
        
        # Create server parameters with mock credentials
        server_params = StdioServerParameters(
            command="python",
            args=[str(crm_server_path), "--instance-url", "mock", "--instance-api-key", "mock"]
        )
        
        # Create a session to get tool information
        async with stdio_client(server_params) as (read, write):
            session = ClientSession(read, write)
            
            print("🔧 Loading MCP tools...")
            
            # Get the tools list
            tools = await load_mcp_tools(session)
            
            print(f"✅ Successfully loaded {len(tools)} tools!")
            print("\n" + "="*60)
            print("📋 AVAILABLE TOOLS")
            print("="*60)
            
            # Extract and display tool information
            for i, tool in enumerate(tools, 1):
                print(f"\n{i:2d}. {tool.name}")
                print(f"    Description: {tool.description}")
                
                # Show schema if available
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    schema = tool.args_schema.schema()
                    if schema.get('properties'):
                        print(f"    Parameters:")
                        for param_name, param_info in schema['properties'].items():
                            param_type = param_info.get('type', 'unknown')
                            param_desc = param_info.get('description', 'No description')
                            print(f"      - {param_name} ({param_type}): {param_desc}")
                    else:
                        print(f"    Parameters: None")
                else:
                    print(f"    Parameters: Not available")
                
                print(f"    Returns: {tool.return_direct if hasattr(tool, 'return_direct') else 'Standard response'}")
            
            print("\n" + "="*60)
            print(f"📊 Total tools discovered: {len(tools)}")
            print("="*60)
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you have installed the required packages:")
        print("   pip install mcp langchain-mcp-adapters")
    except Exception as e:
        print(f"❌ Error discovering tools: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point."""
    print("🚀 MCP Tool Discovery Script")
    print("="*40)
    
    # Check if we're in the right directory
    if not Path("servers/crm_server.py").exists():
        print("❌ Please run this script from the mcp-server directory")
        print("   Expected structure:")
        print("   mcp-server/")
        print("   ├── discover_tools.py")
        print("   └── servers/")
        print("       └── crm_server.py")
        return
    
    # Run the async discovery
    asyncio.run(discover_tools())

if __name__ == "__main__":
    main()
