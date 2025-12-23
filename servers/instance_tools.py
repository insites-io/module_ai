import requests
import json
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import jwt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstanceTools:
    """Instance Management Tools for PlatformOS instance operations."""
    
    def __init__(
        self, 
        aws_create_instance_url: str, 
        aws_instance_jwt_secret: str,
        console_base_url: str = "",
        console_csrf_token: str = ""
    ):
        self.aws_create_instance_url = aws_create_instance_url
        self.aws_instance_jwt_secret = aws_instance_jwt_secret
        self.console_base_url = console_base_url
        self.console_csrf_token = console_csrf_token
    
    def _create_jwt_payload(self, data: Dict[str, Any]) -> tuple:
        """Create JWT payload with timestamp."""
        timestamp = str(int(time.time()))
        payload = {
            "timestamp": timestamp,
            **data
        }
        return payload, timestamp
    
    def _encrypt_token(self, token: str, secret_key: str) -> str:
        """Encrypt JWT token using AES-256-CBC to match PlatformOS encrypt filter format.
        
        PlatformOS encrypt filter format:
        - Removes dashes from secret_key
        - Takes first 32 characters as encryption key
        - Returns base64-encoded encrypted data (IV prepended to ciphertext)
        """
        # Remove dashes and take first 32 chars for encryption key (matching Liquid: remove: "-" | limit: 32)
        encryption_key_str = secret_key.replace("-", "")[:32]
        
        # Convert to bytes and pad to 32 bytes if needed
        encryption_key = encryption_key_str.encode('utf-8')
        if len(encryption_key) < 32:
            encryption_key = encryption_key.ljust(32, b'\0')
        elif len(encryption_key) > 32:
            encryption_key = encryption_key[:32]
        
        # Generate random IV
        from Crypto.Random import get_random_bytes
        iv = get_random_bytes(16)  # AES block size is 16 bytes
        
        # Create cipher with IV
        cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
        
        # Encrypt token (pad to block size)
        token_bytes = pad(token.encode('utf-8'), AES.block_size)
        ct_bytes = cipher.encrypt(token_bytes)
        
        # Combine IV and ciphertext, then base64 encode (PlatformOS format)
        # PlatformOS encrypt filter returns: base64(iv + ciphertext)
        combined = iv + ct_bytes
        encrypted_value = base64.b64encode(combined).decode('utf-8')
        
        return encrypted_value
    
    def _create_authorization_header(self) -> str:
        """Create the Authorization header with encrypted JWT token for AWS Gateway."""
        # Create payload with timestamp
        timestamp = str(int(time.time()))
        payload = {"timestamp": timestamp}
        
        # Encode JWT
        token = jwt.encode(payload, self.aws_instance_jwt_secret, algorithm='HS256')
        
        # Encrypt token
        encrypted_token = self._encrypt_token(token, self.aws_instance_jwt_secret)
        
        return encrypted_token
    
    def _get_console_headers(self) -> Dict[str, str]:
        """Get headers for Console API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }
        if self.console_csrf_token:
            headers["X-CSRF-Token"] = self.console_csrf_token
        return headers
    
    # ============================================================================
    # CONSOLE API METHODS (Frontend validation + Direct database save)
    # ============================================================================
    
    def check_subdomain_availability(self, subdomain: str) -> Dict[str, Any]:
        """
        Check subdomain availability via Console API (frontend validation).
        This does NOT save to database, only validates.
        
        Endpoint: GET /console/subdomain/check
        
        Args:
            subdomain: The subdomain to check
        
        Returns:
            Dict with availability status
        """
        logger.info(f"[Console API] Checking subdomain availability: {subdomain}")
        
        if not self.console_base_url:
            return {
                "success": False,
                "error": "Console URL not configured. Set console_base_url parameter."
            }
        
        try:
            url = f"{self.console_base_url}/console/subdomain/check"
            headers = self._get_console_headers()
            params = {"name": subdomain}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                is_available = result.get("available", False)
                
                logger.info(f"[Console API] Subdomain '{subdomain}' availability: {is_available}")
                return {
                    "success": True,
                    "available": is_available,
                    "subdomain": subdomain,
                    "result": result,
                    "message": f"Subdomain '{subdomain}' is {'available' if is_available else 'unavailable'}",
                    "api": "console"
                }
            else:
                logger.warning(f"[Console API] Check failed. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "subdomain": subdomain,
                    "api": "console"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds", "api": "console"}
        except Exception as e:
            logger.error(f"[Console API] Check error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "subdomain": subdomain,
                "api": "console"
            }
    
    def create_instance_console(
        self,
        name: str,
        subdomain: str,
        environment: str,
        instance_data_centre: str,
        instance_billing_plan: str,
        tags: Optional[List[str]] = None,
        pay_on_invoice: bool = False,
        domain_ids: Optional[List[str]] = None,
        image: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create instance via Console API (direct database save).
        
        Endpoint: POST /api/console/instances
        Saves subdomain to database via GraphQL mutation (line 36 of create_instance.graphql)
        
        Args:
            name: Instance name
            subdomain: Instance subdomain
            environment: 'Staging' or 'Production'
            instance_data_centre: Data centre ID
            instance_billing_plan: Billing plan ID
            tags: Optional list of tags
            pay_on_invoice: Payment method
            domain_ids: Optional domain IDs
            image: Optional image URL or base64
        
        Returns:
            Dict with creation result
        """
        logger.info(f"[Console API] Creating instance: {subdomain}")
        
        if not self.console_base_url:
            return {
                "success": False,
                "error": "Console URL not configured. Set console_base_url parameter."
            }
        
        # Step 1: Check subdomain availability
        logger.info(f"[Console API] Step 1: Checking subdomain availability")
        availability_check = self.check_subdomain_availability(subdomain)
        
        if not availability_check.get("success"):
            return {
                "success": False,
                "error": "Subdomain availability check failed",
                "check_result": availability_check
            }
        
        if not availability_check.get("available"):
            return {
                "success": False,
                "error": f"Subdomain '{subdomain}' is not available",
                "check_result": availability_check
            }
        
        logger.info(f"[Console API] Subdomain available. Proceeding with creation.")
        
        # Step 2: Create instance
        try:
            url = f"{self.console_base_url}/api/console/instances"
            headers = self._get_console_headers()
            
            payload = {
                "payload": {
                    "properties": {
                        "name": name,
                        "subdomain": subdomain,
                        "tags": tags or [],
                        "path": "/root",
                        "domain_ids": domain_ids or [],
                        "type": "instance",
                        "environment": environment,
                        "instance_data_centre": instance_data_centre,
                        "instance_billing_plan": instance_billing_plan,
                        "status": "Initialising"
                    },
                    "pay_on_invoice": pay_on_invoice
                }
            }
            
            if image:
                payload["payload"]["properties"]["image"] = image
            
            logger.info(f"[Console API] Sending create request")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    logger.info(f"[Console API] Instance created successfully: {subdomain}")
                    return {
                        "success": True,
                        "subdomain": subdomain,
                        "result": result,
                        "message": f"Instance '{subdomain}' created successfully via Console API",
                        "saved_to_database": True,
                        "api": "console"
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response from Console API",
                        "status_code": response.status_code,
                        "api": "console"
                    }
            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("errors", [{}])[0].get("message", "Instance creation failed")
                logger.warning(f"[Console API] Creation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "details": error_data,
                    "status_code": 400,
                    "api": "console"
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized. You do not have the necessary permissions to access this account.",
                    "status_code": 401,
                    "api": "console"
                }
            else:
                logger.warning(f"[Console API] Creation failed. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "subdomain": subdomain,
                    "api": "console"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 60 seconds", "api": "console"}
        except Exception as e:
            logger.error(f"[Console API] Creation error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "subdomain": subdomain,
                "api": "console"
            }
    
    # ============================================================================
    # AWS GATEWAY METHODS (Step function validation + creation)
    # ============================================================================
    
    def validate_subdomain(self, subdomain: str) -> Dict[str, Any]:
        """
        Validate subdomain availability via AWS Gateway (step function validation).
        This does NOT save to database, only validates.
        
        Endpoint: GET /Staging/subdomain-check
        
        Args:
            subdomain: The subdomain to validate
        
        Returns:
            Dict with validation result
        """
        logger.info(f"[AWS Gateway] Validating subdomain: {subdomain}")
        
        try:
            # Create authorization header
            auth_token = self._create_authorization_header()
            
            # Prepare validation URL
            url = f"{self.aws_create_instance_url}/Staging/subdomain-check"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_token
            }
            
            params = {"subdomain": subdomain}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                is_available = result.get("status") == "available"
                
                logger.info(f"[AWS Gateway] Subdomain validation result: {result}")
                return {
                    "success": True,
                    "result": result,
                    "subdomain": subdomain,
                    "available": is_available,
                    "message": f"Subdomain '{subdomain}' is {'available' if is_available else 'unavailable'}",
                    "api": "aws_gateway"
                }
            else:
                logger.warning(f"[AWS Gateway] Validation failed. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "subdomain": subdomain,
                    "api": "aws_gateway"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds", "api": "aws_gateway"}
        except Exception as e:
            logger.error(f"[AWS Gateway] Validation error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "subdomain": subdomain,
                "api": "aws_gateway"
            }
    
    def create_instance(self, instance_data: Dict[str, Any], environment: str = "production") -> Dict[str, Any]:
        """
        Create a new PlatformOS instance via AWS Gateway (step function flow).
        Validates subdomain first, then creates and saves to database.
        
        Endpoint: POST /Staging/create-instance
        
        Args:
            instance_data: Dictionary containing:
                - subdomain: The subdomain for the instance (required)
                - pos_billing_plan_id: POS billing plan ID (required)
                - pos_data_centre_id: POS data centre ID (required)
                - tags: List of tags (optional)
                - created_by: User who created the instance (optional)
                - is_duplication: Whether this is a duplication (optional, default: false)
            environment: Environment ('staging' or 'production')
        
        Returns:
            Dict with creation result
        """
        logger.info(f"[AWS Gateway] Creating instance with data: {instance_data}")
        
        # Validate required fields
        required_fields = ["subdomain", "pos_billing_plan_id", "pos_data_centre_id"]
        missing_fields = [field for field in required_fields if field not in instance_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }
        
        subdomain = instance_data["subdomain"]
        
        # Step 1: Validate subdomain
        logger.info(f"[AWS Gateway] Step 1: Validating subdomain '{subdomain}'")
        validation_result = self.validate_subdomain(subdomain)
        
        if not validation_result["success"]:
            return {
                "success": False,
                "error": "Subdomain validation failed",
                "validation_result": validation_result
            }
        
        # Check if subdomain is available
        if not validation_result.get("available", False):
            return {
                "success": False,
                "error": f"Subdomain '{subdomain}' is not available",
                "validation_result": validation_result
            }
        
        logger.info(f"[AWS Gateway] Subdomain '{subdomain}' is available. Proceeding with instance creation.")
        
        # Step 2: Create instance
        try:
            # Create authorization header
            auth_token = self._create_authorization_header()
            
            # Use Staging endpoint for both environments (as per your code)
            endpoint = f"{self.aws_create_instance_url}/Staging/create-instance"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_token
            }
            
            # Prepare payload
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            payload = {
                "metadata": {
                    "request_time": current_time,
                    "request_environment": environment,
                    "request_full_url": instance_data.get("request_full_url", "console-uat.staging.oregon.platform-os.com"),
                    "request_ip": instance_data.get("request_ip", ""),
                    "request_user_id": instance_data.get("request_user_id", "54")
                },
                "properties": {
                    "partner_id": instance_data.get("partner_id", "11"),
                    "pos_billing_plan_id": "246",
                    "pos_data_centre_id": "8",
                    "instance_params": {
                        "name": subdomain,
                        "tag_list": ",".join(instance_data.get("tags", []))
                    },
                    "created_by": instance_data.get("created_by", "enrique@insites.io"),
                    "is_duplication": str(instance_data.get("is_duplication", "false")).lower()
                }
            }
            
            logger.info(f"[AWS Gateway] Sending create instance request to: {endpoint}")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    logger.info(f"[AWS Gateway] Instance created successfully: {subdomain}")
                    return {
                        "success": True,
                        "result": result,
                        "subdomain": subdomain,
                        "message": f"Instance '{subdomain}' created successfully via AWS Gateway",
                        "saved_to_database": True,
                        "api": "aws_gateway"
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response from create instance API",
                        "status_code": response.status_code,
                        "api": "aws_gateway"
                    }
            else:
                logger.warning(f"[AWS Gateway] Failed to create instance. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "subdomain": subdomain,
                    "api": "aws_gateway"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 60 seconds", "api": "aws_gateway"}
        except Exception as e:
            logger.error(f"[AWS Gateway] Error creating instance: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "subdomain": subdomain,
                "api": "aws_gateway"
            }
    
    # ============================================================================
    # LANGCHAIN TOOLS
    # ============================================================================
    
    def get_langchain_tools(self) -> List:
        """Convert Instance methods to LangChain tools."""
        from langchain_core.tools import tool
        
        tools = []
        
        # Console API Tools
        @tool
        def check_subdomain_availability(subdomain: str) -> str:
            """Check subdomain availability via Console API (frontend validation).
            Does NOT save to database, only validates.
            
            Args:
                subdomain: The subdomain to check (e.g., 'my-new-site')
            
            Returns:
                JSON string with availability status
            """
            result = self.check_subdomain_availability(subdomain)
            return json.dumps(result, indent=2)
        
        @tool
        def create_instance_console(instance_data: str) -> str:
            """Create instance via Console API (direct database save).
            
            Workflow:
            1. Check subdomain availability
            2. Create instance and save to database via GraphQL mutation
            
            Args:
                instance_data: JSON string containing:
                    - name: Instance name (required)
                    - subdomain: Instance subdomain (required)
                    - environment: 'Staging' or 'Production' (required)
                    - instance_data_centre: Data centre ID (required)
                    - instance_billing_plan: Billing plan ID (required)
                    - tags: List of tags (optional)
                    - pay_on_invoice: Payment method (optional, default: false)
                    - domain_ids: Domain IDs (optional)
                    - image: Image URL or base64 (optional)
            
            Example:
                {
                    "name": "My Instance",
                    "subdomain": "my-instance",
                    "environment": "Staging",
                    "instance_data_centre": "dc_123",
                    "instance_billing_plan": "plan_456",
                    "tags": ["production"]
                }
            """
            try:
                data = json.loads(instance_data) if isinstance(instance_data, str) else instance_data
                result = self.create_instance_console(
                    name=data["name"],
                    subdomain=data["subdomain"],
                    environment=data["environment"],
                    instance_data_centre=data["instance_data_centre"],
                    instance_billing_plan=data["instance_billing_plan"],
                    tags=data.get("tags"),
                    pay_on_invoice=data.get("pay_on_invoice", False),
                    domain_ids=data.get("domain_ids"),
                    image=data.get("image")
                )
                return json.dumps(result, indent=2)
            except (json.JSONDecodeError, KeyError) as e:
                return json.dumps({"success": False, "error": f"Invalid input: {str(e)}"}, indent=2)
        
        # AWS Gateway Tools
        @tool
        def validate_subdomain(subdomain: str) -> str:
            """Validate subdomain via AWS Gateway (step function validation).
            Does NOT save to database, only validates.
            
            Args:
                subdomain: The subdomain to check (e.g., 'my-new-site')
            
            Returns:
                JSON string with validation result indicating if subdomain is available
            """
            result = self.validate_subdomain(subdomain)
            return json.dumps(result, indent=2)
        
        @tool
        def create_instance(instance_data: str, environment: str = "production") -> str:
            """Create instance via AWS Gateway (step function flow).
            
            Workflow:
            1. Validate subdomain availability
            2. Create instance via step function and save to database
            
            Args:
                instance_data: JSON string containing:
                    - subdomain: The subdomain for the instance (required)
                    - pos_billing_plan_id: POS billing plan ID (required)
                    - pos_data_centre_id: POS data centre ID (required)
                    - tags: List of tags (optional)
                    - created_by: User who created the instance (optional)
                    - is_duplication: Whether this is a duplication (optional)
                environment: 'staging' or 'production' (default: 'production')
            
            Example:
                {
                    "subdomain": "my-new-site",
                    "pos_billing_plan_id": "246",
                    "pos_data_centre_id": "8",
                    "tags": ["production", "client-a"],
                    "created_by": "user@example.com"
                }
            """
            try:
                data = json.loads(instance_data) if isinstance(instance_data, str) else instance_data
                result = self.create_instance(data, environment)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        tools.extend([
            check_subdomain_availability,
            create_instance_console,
            validate_subdomain,
            create_instance
        ])
        
        return tools