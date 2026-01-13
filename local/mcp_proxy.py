import sys
import os
import json
import requests
import traceback

CLOUD_RUN_URL = os.environ.get("SERVER_URL")
INSITES_INSTANCE_URL = os.environ.get("INSITES_INSTANCE_URL")
INSITES_INSTANCE_API_KEY = os.environ.get("INSITES_INSTANCE_API_KEY")
CONSOLE_EMAIL = os.environ.get("CONSOLE_EMAIL", "") 

if not CLOUD_RUN_URL:
    print("SERVER_URL (Cloud Run URL) is not set", file=sys.stderr)
    sys.exit(1)

# Ensure URL doesn't end with /
CLOUD_RUN_URL = CLOUD_RUN_URL.rstrip('/')


def send_error(request_id, code, message, data=None):
    """Send a JSON-RPC 2.0 compliant error response"""
    # Don't send error responses for notifications (requests without id)
    if request_id is None:
        return
    
    error_response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }
    if data is not None:
        error_response["error"]["data"] = data
    print(json.dumps(error_response), flush=True)


def send_response(request_id, result):
    """Send a JSON-RPC 2.0 compliant success response"""
    # Don't send responses for notifications (requests without id)
    if request_id is None:
        return
    
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }
    print(json.dumps(response), flush=True)


def handle_initialize(request_id, params):
    """Handle MCP initialize method"""
    return send_response(request_id, {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "crm-server",
            "version": "1.0.0"
        }
    })


def handle_tools_list(request_id, params):
    """Handle MCP tools/list method by calling Cloud Run REST API"""
    try:
        if not INSITES_INSTANCE_URL or not INSITES_INSTANCE_API_KEY:
            return send_error(
                request_id,
                -32602,
                "INSITES_INSTANCE_URL and INSITES_INSTANCE_API_KEY environment variables must be set"
            )
        
        # Call the Cloud Run REST endpoint with required credentials
        response = requests.post(
            f"{CLOUD_RUN_URL}/mcp/tools/list",
            json={
                "instance_url": INSITES_INSTANCE_URL,
                "instance_api_key": INSITES_INSTANCE_API_KEY
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        # Handle HTTP errors
        if response.status_code != 200:
            return send_error(
                request_id,
                -32000,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            return send_error(
                request_id,
                -32000,
                f"Invalid JSON response from server: {response.text[:200]}"
            )
        
        # Convert REST API response to MCP format
        if "tools" in data:
            tools = data["tools"]
        elif isinstance(data, list):
            tools = data
        else:
            tools = []
        
        return send_response(request_id, {
            "tools": tools
        })
    except requests.exceptions.RequestException as e:
        send_error(
            request_id,
            -32000,
            f"Request failed: {str(e)}"
        )
    except Exception as e:
        send_error(
            request_id,
            -32603,
            f"Internal error: {str(e)}"
        )


def handle_tools_call(request_id, params):
    """Handle MCP tools/call method by calling Cloud Run REST API"""
    try:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return send_error(
                request_id,
                -32602,
                "Missing 'name' parameter"
            )
        
        # Check if this is an instance management tool
        instance_tools = ["validate_subdomain", "create_instance"]
        is_instance_tool = tool_name in instance_tools

        if not INSITES_INSTANCE_URL or not INSITES_INSTANCE_API_KEY:
            return send_error(
                request_id,
                -32602,
                "INSITES_INSTANCE_URL and INSITES_INSTANCE_API_KEY environment variables must be set for CRM tools"
            )
        
        # Prepare query parameters and request body
        query_params = {}
        request_body = {
            "name": tool_name,
            "arguments": arguments.copy()  # Make a copy so we don't modify the original
        }
        
        # # Add credentials to request based on tool type
        if is_instance_tool:
            # For instance tools, add AWS credentials and console credentials to arguments
            if CONSOLE_EMAIL:
                request_body["arguments"]["console_email"] = CONSOLE_EMAIL

        query_params = {
            "instance_url": INSITES_INSTANCE_URL,
            "instance_api_key": INSITES_INSTANCE_API_KEY
        }
        
        # Call the Cloud Run REST endpoint
        response = requests.post(
            f"{CLOUD_RUN_URL}/mcp/tools/call",
            json=request_body,
            params=query_params,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        # Handle HTTP errors
        if response.status_code != 200:
            return send_error(
                request_id,
                -32000,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            return send_error(
                request_id,
                -32000,
                f"Invalid JSON response from server: {response.text[:200]}"
            )
        
        # Convert REST API response to MCP format
        if "content" in data:
            content = data["content"]
        else:
            content = [{
                "type": "text",
                "text": json.dumps(data, indent=2)
            }]
        
        return send_response(request_id, {
            "content": content,
            "isError": data.get("isError", False)
        })
    except requests.exceptions.RequestException as e:
        send_error(
            request_id,
            -32000,
            f"Request failed: {str(e)}"
        )
    except Exception as e:
        send_error(
            request_id,
            -32603,
            f"Internal error: {str(e)}"
        )


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break

        request_id = None
        try:
            # Parse the JSON-RPC request
            line = line.strip()
            if not line:
                continue
                
            request = json.loads(line)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            # Check if this is a notification (id is null/None) - notifications don't get responses
            is_notification = (request_id is None)
            
            # Validate request has required fields
            if method is None:
                # Only send error for non-notifications
                if not is_notification:
                    send_error(
                        request_id,
                        -32600,  # Invalid Request
                        "Missing 'method' field"
                    )
                continue
            
            # Handle different MCP methods
            if method == "initialize":
                handle_initialize(request_id, params)
            elif method == "tools/list":
                handle_tools_list(request_id, params)
            elif method == "tools/call":
                handle_tools_call(request_id, params)
            elif method == "notifications/cancelled":
                # Ignore cancellation notifications (they don't need responses)
                continue
            else:
                # Only send error for non-notifications
                if not is_notification:
                    send_error(
                        request_id,
                        -32601,  # Method not found
                        f"Method not found: {method}"
                    )

        except json.JSONDecodeError as e:
            # For parse errors, we might not have a valid request_id, so check first
            # But parse errors are serious - log to stderr and only respond if we have an id
            print(f"Parse error: {str(e)}", file=sys.stderr)
            if request_id is not None:
                send_error(
                    request_id,
                    -32700,  # Parse error
                    f"Parse error: {str(e)}"
                )
        except Exception as e:
            # Log to stderr for debugging
            print(f"Internal error: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            # Only send error response if we have a valid request_id
            if request_id is not None:
                send_error(
                    request_id,
                    -32603,  # Internal error
                    f"Internal error: {str(e)}"
                )


if __name__ == "__main__":
    main()