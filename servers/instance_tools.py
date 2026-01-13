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
from bs4 import BeautifulSoup
import re
from utils.secret_manager import get_secret, get_secret_manager
import uuid 
import os
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstanceTools:
    """Instance Management Tools for PlatformOS instance operations."""
    
    def __init__(
        self, 
        console_email: str = "",
    ):
        self.console_email = console_email
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
        
        from Crypto.Random import get_random_bytes
        iv = get_random_bytes(16)
        cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
        token_bytes = pad(token.encode('utf-8'), AES.block_size)
        ct_bytes = cipher.encrypt(token_bytes)
        combined = iv + ct_bytes
        encrypted_value = base64.b64encode(combined).decode('utf-8')
        return encrypted_value
    
    def _create_authorization_header(self) -> str:
        """Create the Authorization header with encrypted JWT token for AWS Gateway."""
        try:
            secret_mgr = get_secret_manager()
            aws_instance_jwt_secret = secret_mgr.get_secret("insites-auth-key-prod")
            timestamp = str(int(time.time()))
            payload = {"timestamp": timestamp}
            token = jwt.encode(payload, aws_instance_jwt_secret, algorithm='HS256')
            encrypted_token = self._encrypt_token(token, aws_instance_jwt_secret)
            return encrypted_token
        except Exception as e:
            logger.error(f"❌ Failed to create authorization header: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Failed to retrieve AWS JWT secret from Secret Manager: {str(e)}")

    def create_instance_database(
        self,
        name: str,
        subdomain: str,
        contact_uuid: str,
        default_domain: str = "staging.oregon.platform-os.com"
    ) -> Dict[str, Any]:
        """
        Create an instance record in the database via Console API.
        
        Endpoint: POST https://console.insites.io/databases/api/v2/database/19410/items
        
        Args:
            name: Instance name (e.g., "test_claude_4")
                - Will be converted to URL format: underscores to hyphens, lowercase
                - Example: "test_claude_4" -> "test-claude-4"
            default_domain: Default domain to append (default: "staging.oregon.platform-os.com")
                - Final URL will be: "{converted_name}.{default_domain}"
        
        Returns:
            Dict with creation result
        """
        logger.info(f"[Database API] Creating instance record: {subdomain}")
        secret_mgr = get_secret_manager()
        console_api_key = secret_mgr.get_secret("console-instance-api-key")
        if not console_api_key:
            return {
                "success": False,
                "error": "Instance API key not configured"
            }
        
        # Convert name to URL format: underscores to hyphens, lowercase
        url_name = re.sub(r"[\s_]+", "-", subdomain).lower()
        instance_url = f"{url_name}.{default_domain}"
        
        logger.info(f"[Database API] Name: {subdomain} -> URL: {instance_url}")
        
        # Database API endpoint
        api_url = "https://console.insites.io/databases/api/v2/database/19410/items"
        
        # Headers with instance API key
        headers = {
            "Authorization": console_api_key,
            "Content-Type": "application/json"
        }
        
        # Payload with fixed values except name and url
        payload = {
            "properties.name": name,
            "properties.url": instance_url,
            "properties.type": "instance",
            "properties.environment": "Staging",
            "properties.instance_data_centre": "67",
            "properties.instance_billing_plan": "69",
            "properties.status": "Initialising",
            "properties.account_id": "109",
            "properties.uuid": str(uuid.uuid4()),
            "properties.created_by": contact_uuid,
            "properties.subdomain": subdomain,

        }
        
        try:
            logger.info(f"[Database API] Sending POST request to: {api_url}")
            logger.info(f"[Database API] Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            logger.info(f"[Database API] Response status: {response.status_code}")
            logger.info(f"[Database API] Response Content-Type: {response.headers.get('Content-Type', '')}")
            
            # Check if response is HTML instead of JSON
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type or response.text.strip().startswith('<'):
                logger.error(f"[Database API] ERROR: Got HTML instead of JSON")
                return {
                    "success": False,
                    "error": "Received HTML response instead of JSON",
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "response_preview": response.text[:200]
                }
            
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    logger.info(f"[Database API] Instance record created successfully: {name}")
                    return {
                        "success": True,
                        "name": name,
                        "url": instance_url,
                        "result": result,
                        "message": f"Instance record '{name}' created successfully",
                        "api": "database"
                    }
                except json.JSONDecodeError as json_err:
                    logger.error(f"[Database API] Invalid JSON response: {response.text[:200]}")
                    return {
                        "success": False,
                        "error": f"Invalid JSON response: {str(json_err)}",
                        "status_code": response.status_code,
                        "response_preview": response.text[:500]
                    }
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error") or error_data.get("message", "Bad request")
                except:
                    error_msg = "Bad request"
                    error_data = response.text
                logger.warning(f"[Database API] Creation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "details": error_data,
                    "status_code": 400,
                    "api": "database"
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Unauthorized. Check instance API key.",
                    "status_code": 401,
                    "api": "database"
                }
            else:
                logger.warning(f"[Database API] Creation failed. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:500] if response.text else "No response body",
                    "name": name,
                    "api": "database"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out after 60 seconds",
                "api": "database"
            }
        except Exception as e:
            logger.error(f"[Database API] Creation error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "name": name,
                "api": "database"
            }
    
    def _get_request_user_from_contact(self) -> Dict[str, Any]:
        """
        Get contact information from contact lookup using console_email.
        
        Returns:
            Dict with contact information including 'uuid', 'id', and 'email' keys
        """
        if not self.console_email:
            logger.error("No email provided for contact lookup")
            raise ValueError("No email provided for contact lookup")
        
        try:
            from servers.crm_tools import CRMTools
            
            instance_url = "https://console.insites.io"
            
            # Get API key from Secret Manager
            try:
                secret_mgr = get_secret_manager()
                instance_api_key = secret_mgr.get_secret("console-instance-api-key")
            except Exception as secret_error:
                logger.error(f"❌ Failed to get console API key from Secret Manager: {secret_error}")
                raise ValueError(f"Failed to retrieve console-instance-api-key from Secret Manager: {str(secret_error)}")
            
            crm_tools = CRMTools(instance_url, instance_api_key)
            params = {
                "search_by": "email",
                "keyword": self.console_email,
                "size": 1,
                "page": 1
            }
            
            contact_result = crm_tools.get_contacts(params)
            
            if not contact_result.get("success"):
                error_msg = contact_result.get("error", "Unknown error fetching contact")
                logger.error(f"❌ Failed to fetch contact: {error_msg}")
                raise ValueError(f"Failed to fetch contact: {error_msg}")
            
            # Handle different response structures
            result_data = contact_result.get("result", {})
            
            # Try different possible structures
            contacts = None
            if isinstance(result_data, list):
                contacts = result_data
            elif isinstance(result_data, dict):
                if "results" in result_data:
                    contacts = result_data["results"]
                elif "data" in result_data:
                    contacts = result_data["data"] if isinstance(result_data["data"], list) else [result_data["data"]]
                elif "contacts" in result_data:
                    contacts = result_data["contacts"]
            
            if not contacts or len(contacts) == 0:
                logger.error(f"❌ No contact found for email: {self.console_email}")
                raise ValueError(f"No contact found for email: {self.console_email}")
            
            contact = contacts[0]
            
            # Ensure required fields exist
            if "uuid" not in contact or "id" not in contact:
                logger.error(f"❌ Contact found but missing required fields (uuid/id). Available keys: {list(contact.keys())}")
                raise ValueError(f"Contact found but missing required fields (uuid/id)")
            
            logger.info(f"✅ Found contact: email={contact.get('email', self.console_email)}")
            return contact
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ Error fetching contact: {e}")
            raise ValueError(f"Failed to fetch contact for {self.console_email}: {str(e)}")
    # ============================================================================
    # AWS GATEWAY METHODS (Step function validation + creation)
    # ============================================================================
    
    def validate_subdomain(self, name: str) -> Dict[str, Any]:
        """Validate subdomain availability via AWS Gateway (step function validation)."""
        subdomain = re.sub(r"[\s_]+", "-", name).lower()
        logger.info(f"[VALIDATE_SUBDOMAIN] Normalized subdomain: {subdomain}")

        try:
            logger.info(f"[VALIDATE_SUBDOMAIN] Step 1: Getting auth token...")
            try:
                auth_token = self._create_authorization_header()
                logger.info(f"[VALIDATE_SUBDOMAIN] ✅ Auth token created (length: {len(auth_token)})")
            except Exception as auth_error:
                error_msg = f"Failed to authenticate: {str(auth_error)}"
                logger.error(f"❌ [VALIDATE_SUBDOMAIN] {error_msg}")
                import sys
                sys.stdout.flush()
                sys.stderr.flush()
                return {
                    "success": False,
                    "error": error_msg,
                    "subdomain": subdomain,
                    "api": "aws_gateway",
                    "error_type": "authentication_failed"
                }
            
            # Get subdomain check URL from Secret Manager
            logger.info(f"[VALIDATE_SUBDOMAIN] Step 2: Getting subdomain check URL from Secret Manager...")
            try:
                secret_mgr = get_secret_manager()
                subdomain_check = secret_mgr.get_secret("insites-validate-subdomain-prod")
                url = subdomain_check
                logger.info(f"[VALIDATE_SUBDOMAIN] ✅ Retrieved URL: {url[:50]}...")
            except Exception as secret_error:
                error_msg = f"Failed to retrieve subdomain check URL from Secret Manager: {str(secret_error)}"
                logger.error(f"❌ [VALIDATE_SUBDOMAIN] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "subdomain": subdomain,
                    "api": "aws_gateway",
                    "error_type": "secret_not_found",
                    "secret_name": "insites-validate-subdomain-prod"
                }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_token
            }
            params = {"subdomain": subdomain}
            
            logger.info(f"[VALIDATE_SUBDOMAIN] Step 3: Making GET request to AWS Gateway...")
            logger.info(f"[VALIDATE_SUBDOMAIN] URL: {url}")
            logger.info(f"[VALIDATE_SUBDOMAIN] Params: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            logger.info(f"[VALIDATE_SUBDOMAIN] Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                is_available = result.get("status") == "available"
                logger.info(f"[VALIDATE_SUBDOMAIN] ✅ Success - Subdomain '{subdomain}' is {'available' if is_available else 'unavailable'}")
                return {
                    "success": True,
                    "result": result,
                    "subdomain": subdomain,
                    "available": is_available,
                    "message": f"Subdomain '{subdomain}' is {'available' if is_available else 'unavailable'}",
                    "api": "aws_gateway"
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                logger.error(f"❌ [VALIDATE_SUBDOMAIN] Validation failed: {error_msg}")

                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:500],
                    "subdomain": subdomain,
                    "api": "aws_gateway",
                    "error_type": "http_error"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": error_msg,
                "subdomain": subdomain,
                "api": "aws_gateway",
                "error_type": "timeout"
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [VALIDATE_SUBDOMAIN] Unexpected error: {error_msg}")

            return {
                "success": False,
                "error": error_msg,
                "subdomain": subdomain,
                "api": "aws_gateway",
                "error_type": "unexpected_error"
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
        
        required_fields = ["subdomain"]
        missing_fields = [field for field in required_fields if field not in instance_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }
        
        subdomain = instance_data["subdomain"]
        
        logger.info(f"[AWS Gateway] Step 1: Validating subdomain '{subdomain}'")

        validation_result = self.validate_subdomain(name=subdomain)
        
        if not validation_result["success"]:
            return {
                "success": False,
                "error": "Subdomain validation failed",
                "validation_result": validation_result
            }
        
        if not validation_result.get("available", False):
            return {
                "success": False,
                "error": f"Subdomain '{subdomain}' is not available",
                "validation_result": validation_result
            }
        
        logger.info(f"[AWS Gateway] Subdomain '{subdomain}' is available. Proceeding with instance creation.")

        try:
            # Get auth token (this uses Secret Manager)
            try:
                auth_token = self._create_authorization_header()
            except Exception as auth_error:
                logger.error(f"❌ Failed to get auth token: {auth_error}")
                return {
                    "success": False,
                    "error": f"Failed to authenticate: {str(auth_error)}",
                    "subdomain": subdomain,
                    "api": "aws_gateway"
                }
            
            # Get create instance endpoint from Secret Manager
            try:
                secret_mgr = get_secret_manager()
                endpoint = secret_mgr.get_secret("insites-create-instance-prod")
            except Exception as secret_error:
                logger.error(f"❌ Failed to get create instance endpoint: {secret_error}")
                return {
                    "success": False,
                    "error": f"Failed to retrieve create instance endpoint from Secret Manager: {str(secret_error)}",
                    "subdomain": subdomain,
                    "api": "aws_gateway"
                }
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_token
            }
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {
                "metadata": {
                    "request_time": current_time,
                    "request_environment": "Staging",
                    "request_full_url": "console.insites.io",
                    "request_ip": instance_data.get("request_ip", ""),
                    "request_user_id": instance_data.get("request_user_id", "76")
                },
                "properties": {
                    "partner_id": instance_data.get("partner_id", "11"),
                    "pos_billing_plan_id": "246",
                    "pos_data_centre_id": "8",
                    "instance_params": {
                        "name": subdomain,
                        "tag_list": ",".join(instance_data.get("tags", []))
                    },
                    "created_by": instance_data.get("created_by"),
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
    
    def create_instance_complete_workflow(
        self,
        name: str,
        environment: str = "production",
    ) -> Dict[str, Any]:
        """
        Complete instance creation workflow:
        1. Check subdomain availability
        2. Save to database via Database API - CRUCIAL STEP
        3. Update via AWS Gateway step function (create_instance)
        
        The Console API creates the initial database record which is then
        updated by the step function.
        
        Args:
            name: Instance name (will be converted to subdomain format)
            environment: 'staging' or 'production' (default: 'production')
        
        Returns:
            Dict with complete workflow result
        """
        try:
            if not name:
                return {
                    "success": False,
                    "error": "Instance name is required",
                    "workflow_results": {}
                }
            
            # Normalize environment (capitalize first letter)
            environment = environment.capitalize()
            
            subdomain = re.sub(r"[\s_]+", "-", name).lower()

            logger.info(f"[CREATE_INSTANCE_WORKFLOW] Starting for name: '{name}', subdomain: '{subdomain}', environment: '{environment}'")
            
            workflow_results = {"subdomain": subdomain, "name": name, "steps": {}}
            
            # Step 1: Check subdomain availability
            logger.info(f"[CREATE_INSTANCE_WORKFLOW] Step 1: Checking subdomain availability")
            availability_check = self.validate_subdomain(name)
            workflow_results["steps"]["1_availability_check"] = availability_check
            
            if not availability_check.get("success"):
                error_msg = availability_check.get("error", "Unknown error")
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] Step 1 failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Subdomain validation failed: {error_msg}",
                    "workflow_results": workflow_results
                }
            
            if not availability_check.get("available"):
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] Subdomain '{subdomain}' is not available")
                return {
                    "success": False,
                    "error": f"Subdomain '{subdomain}' is not available",
                    "workflow_results": workflow_results
                }
            
            # Step 2: Create database record via Console API
            logger.info(f"[CREATE_INSTANCE_WORKFLOW] Step 2: Creating database record via Console API")
            try:
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] Getting contact information...")
                contact = self._get_request_user_from_contact()
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] ✅ Contact retrieved: {contact.get('email', 'N/A')}")
            except ValueError as contact_error:
                error_msg = f"Failed to get contact information: {str(contact_error)}"
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] {error_msg}")

                return {
                    "success": False,
                    "error": error_msg,
                    "workflow_results": workflow_results
                }

            try:
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] Creating database record...")
                console_creation = self.create_instance_database(
                    name=name,
                    subdomain=subdomain,
                    contact_uuid=contact["uuid"],
                )
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] Database creation result: success={console_creation.get('success', False)}")
            except Exception as db_error:
                error_msg = f"Failed to create database record: {str(db_error)}"
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] {error_msg}")

                return {
                    "success": False,
                    "error": error_msg,
                    "workflow_results": workflow_results
                }
            
            workflow_results["steps"]["2_console_creation"] = console_creation

            if not console_creation.get("success"):
                error_msg = console_creation.get('error', 'Unknown error')
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] Step 2 failed: {error_msg}")

                return {
                    "success": False,
                    "error": f"Failed to create database record via Console API: {error_msg}",
                    "workflow_results": workflow_results
                }

            # Validate console_creation result structure
            console_result = console_creation.get("result")
            if not console_result:
                return {
                    "success": False,
                    "error": "Database creation returned no result",
                    "workflow_results": workflow_results
                }
            
            console_properties = console_result.get("properties") if isinstance(console_result, dict) else {}
            if not console_properties:
                logger.warning("⚠️  Console creation result missing properties, using defaults")
                console_properties = {}

            logger.info(f"[CREATE_INSTANCE_WORKFLOW] ✅ Database record created successfully")

            # Step 3: Update via AWS Gateway
            logger.info(f"[CREATE_INSTANCE_WORKFLOW] Step 3: Updating via AWS Gateway")

            gateway_instance_data = {
                "subdomain": subdomain,
                "pos_billing_plan_id": console_properties.get("instance_billing_plan", "69"),
                "pos_data_centre_id": console_properties.get("instance_data_centre", "67"),
                "tags": [],
                "created_by": contact.get("email", self.console_email),
                "is_duplication": False,
                "request_full_url": console_properties.get("url", f"{subdomain}.staging.oregon.platform-os.com"),
                "request_ip": "",
                "request_user_id": str(contact.get("id", "76")),
                "partner_id": "11"
            }
            
            try:
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] Calling create_instance with gateway_instance_data...")
                gateway_result = self.create_instance(gateway_instance_data, environment)
                logger.info(f"[CREATE_INSTANCE_WORKFLOW] Gateway result: success={gateway_result.get('success', False)}")
            except Exception as gateway_error:
                error_msg = f"Failed to create instance via AWS Gateway: {str(gateway_error)}"
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] {error_msg}")

                gateway_result = {
                    "success": False,
                    "error": error_msg
                }
            
            workflow_results["steps"]["3_gateway_update"] = gateway_result
            
            # Check if gateway step succeeded
            if not gateway_result.get("success", False):
                error_msg = gateway_result.get('error', 'Unknown error')
                logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] Step 3 failed: {error_msg}")

                return {
                    "success": False,
                    "error": f"Instance creation workflow completed but AWS Gateway step failed: {error_msg}",
                    "subdomain": subdomain,
                    "workflow_results": workflow_results,
                    "database_saved": True,
                    "step_function_updated": False
                }
            
            logger.info(f"[CREATE_INSTANCE_WORKFLOW] ✅ All steps completed successfully!")
            return {
                "success": True,
                "subdomain": subdomain,
                "name": name,
                "message": f"Instance '{name}' (subdomain: '{subdomain}') created successfully",
                "workflow_results": workflow_results,
                "database_saved": True,
                "step_function_updated": gateway_result.get("success", False)
            }
        except Exception as workflow_error:
            error_msg = f"Workflow failed: {str(workflow_error)}"
            logger.error(f"❌ [CREATE_INSTANCE_WORKFLOW] {error_msg}")

            return {
                "success": False,
                "error": error_msg,
                "workflow_results": workflow_results if 'workflow_results' in locals() else {},
            }
    
    # ============================================================================
    # LANGCHAIN TOOLS
    # ============================================================================
    
    def get_langchain_tools(self) -> List:
        """Convert Instance methods to LangChain tools."""
        from langchain_core.tools import tool
        
        tools = []

        @tool
        def validate_subdomain(subdomain: str) -> str:
            """Validate subdomain via AWS Gateway."""
            result = self.validate_subdomain(subdomain)
            return json.dumps(result, indent=2)
        
        @tool
        def create_instance(instance_data: str, environment: str = "production") -> str:
            """Create instance via AWS Gateway."""
            try:
                data = json.loads(instance_data) if isinstance(instance_data, str) else instance_data
                result = self.create_instance(data, environment)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def create_instance_complete_workflow(instance_data: str, environment: str = "staging") -> str:
            """Complete instance creation workflow (RECOMMENDED METHOD)."""
            try:
                data = json.loads(instance_data) if isinstance(instance_data, str) else instance_data
                result = self.create_instance_complete_workflow(
                    name=data["name"],
                    environment=data["environment"],
                )
                return json.dumps(result, indent=2)
            except (json.JSONDecodeError, KeyError) as e:
                return json.dumps({"success": False, "error": f"Invalid input: {str(e)}"}, indent=2)
        
        tools.extend([
            validate_subdomain,
            create_instance,
            create_instance_complete_workflow
        ])
        
        return tools