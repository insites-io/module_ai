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
        console_csrf_token: str = "",
        console_username: str = "",
        console_password: str = "",
        console_account_id: str = "1510"
    ):
        self.aws_create_instance_url = aws_create_instance_url
        self.aws_instance_jwt_secret = aws_instance_jwt_secret
        self.console_base_url = console_base_url
        self.console_csrf_token = console_csrf_token
        self.console_username = console_username
        self.console_password = console_password
        self.session = None  # Will hold authenticated session
        self._csrf_token_cache = None  # Cache the CSRF token
        self.console_account_id = console_account_id 
    
    def _get_csrf_token_via_login(self) -> Optional[str]:
        """
        Get CSRF token by logging into the console using PlatformOS form builder.
        Complete authentication workflow with proper cookie management:
        1. GET /login → Extract CSRF token and page_id
        2. POST /api/sessions → Login with credentials (receives session cookies)
        3. GET /console → Follow redirect to get console CSRF token
        4. GET /api/console/accounts → Get available account IDs (with cookies)
        5. GET /api/console/accounts/switch?id={{account_id}} → Set active account (with cookies)
        6. Ready to make authenticated API calls (all requests include cookies)
        """
        if not self.console_base_url or not self.console_username or not self.console_password:
            logger.warning("[Console Login] Console credentials not configured for automatic login")
            return None
        
        try:
            logger.info(f"[Console Login] Starting complete authentication workflow for {self.console_base_url}")
            
            # Create a new session
            if not self.session:
                self.session = requests.Session()
            
            # ========================================================================
            # Step 1: GET /login → Extract CSRF token and page_id
            # ========================================================================
            login_url = f"{self.console_base_url}/login"
            logger.info(f"[Console Login] Step 1: Fetching login page: {login_url}")
            
            login_page_response = self.session.get(login_url, timeout=30)
            logger.info(f"[Console Login] Cookies after Step 1: {dict(self.session.cookies)}")
            
            if login_page_response.status_code != 200:
                logger.error(f"[Console Login] Failed to load login page. Status: {login_page_response.status_code}")
                return None
            
            # Parse HTML to extract CSRF token and page_id
            soup = BeautifulSoup(login_page_response.text, 'html.parser')
            
            # Extract CSRF token from meta tag
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if not csrf_meta or not csrf_meta.get('content'):
                logger.error("[Console Login] CSRF token not found in meta tag")
                return None
            
            csrf_token = csrf_meta['content']
            logger.info(f"[Console Login] Found CSRF token: {csrf_token[:30]}...")
            
            # Find the login form to extract page_id
            form = soup.find('form', {'id': 'login-form'}) or soup.find('form')
            if not form:
                logger.error("[Console Login] Login form not found")
                return None
            
            # Extract page_id from hidden input (it's dynamic per page load)
            page_id_input = form.find('input', {'name': 'page_id'})
            page_id = page_id_input.get('value') if page_id_input else ""
            logger.info(f"[Console Login] Found page_id: {page_id}")
            
            # ========================================================================
            # Step 2: POST /api/sessions → Login with credentials
            # ========================================================================
            logger.info(f"[Console Login] Step 2: Submitting login credentials")
            
            # Prepare form data exactly as Postman shows
            form_data = {
                "form[email]": self.console_username,
                "form[password]": self.console_password,
                "authenticity_token": csrf_token,
                "utf8": "✓",  # Checkmark character
                # "form_id": "25901",  # Hardcoded from Postman,
                "form_id": "261748",
                "page_id": page_id,  # Dynamic from login page
                "slug": "login",
                "slug2": "",
                "slug3": "",
                "slugs": "",
                "resource_id": "new",
                "parent_resource_id": "",
                "parent_resource_class": ""
            }
            
            submit_url = f"{self.console_base_url}/api/sessions"
            headers = {
                'X-CSRF-Token': csrf_token,
                'Referer': login_url,
            }
            
            # Session automatically includes cookies from Step 1
            login_response = self.session.post(
                submit_url,
                data=form_data,
                headers=headers,
                allow_redirects=False,
                timeout=30
            )
            
            logger.info(f"[Console Login] Login response status: {login_response.status_code}")
            logger.info(f"[Console Login] Cookies after Step 2: {dict(self.session.cookies)}")
            
            # Check for successful login
            if login_response.status_code not in [200, 201, 301, 302, 303, 307, 308]:
                logger.error(f"[Console Login] Login failed. Status: {login_response.status_code}")
                logger.error(f"[Console Login] Response: {login_response.text[:500]}")
                return None
            
            # ========================================================================
            # Step 3: GET /console → Follow redirect to get console CSRF token
            # ========================================================================
            logger.info(f"[Console Login] Step 3: Following redirect to console")
            
            location = login_response.headers.get('Location', '/console')
            redirect_url = f"{self.console_base_url}{location}" if location.startswith('/') else location
            
            # Session automatically includes cookies from Step 2
            console_response = self.session.get(redirect_url, timeout=30)
            logger.info(f"[Console Login] Cookies after Step 3: {dict(self.session.cookies)}")
            
            # Extract CSRF token from console page
            soup = BeautifulSoup(console_response.text, 'html.parser')
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            
            if not csrf_meta or not csrf_meta.get('content'):
                logger.warning("[Console Login] Could not extract CSRF token from console page")
                console_csrf_token = csrf_token  # Fallback to login token
            else:
                console_csrf_token = csrf_meta['content']
                logger.info(f"[Console Login] Got console CSRF token: {console_csrf_token[:30]}...")
            
            # ========================================================================
            # Step 4: Determine account ID (explicit or from API)
            # ========================================================================
            account_id = None
            
            # PRIORITY 1: Use explicit account_id if provided
            if self.console_account_id:
                account_id = str(self.console_account_id)
                logger.info(f"[Console Login] Using explicit account ID: {account_id}")
            else:
                # PRIORITY 2: Try to fetch from accounts API
                logger.info(f"[Console Login] Step 4: Fetching available accounts")
                
                accounts_url = f"{self.console_base_url}/api/console/accounts"
                accounts_headers = {
                    'X-CSRF-Token': console_csrf_token,
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Cache-Control': 'no-cache'
                }
                
                # Session automatically includes cookies from previous steps
                accounts_response = self.session.get(accounts_url, headers=accounts_headers, timeout=30)
                logger.info(f"[Console Login] Cookies after Step 4: {dict(self.session.cookies)}")
                logger.info(f"[Console Login] Accounts response status: {accounts_response.status_code}")
                
                if accounts_response.status_code == 200:
                    try:
                        accounts_data = accounts_response.json()
                        logger.info(f"[Console Login] Accounts response: {json.dumps(accounts_data, indent=2)[:500]}")
                        
                        # FIXED: Check correct response structure: {"items": {"results": [{"id": "98", ...}]}}
                        if isinstance(accounts_data, dict):
                            items = accounts_data.get('items', {})
                            if isinstance(items, dict):
                                results = items.get('results', [])
                                if isinstance(results, list) and len(results) > 0:
                                    account_id = str(results[0].get('id') or results[0].get('uuid', ''))
                                    logger.info(f"[Console Login] Extracted account ID from API: {account_id}")
                        
                        # Fallback: Check other possible structures
                        if not account_id:
                            if isinstance(accounts_data, list) and len(accounts_data) > 0:
                                account_id = str(accounts_data[0].get('id') or accounts_data[0].get('uuid', ''))
                            elif isinstance(accounts_data, dict):
                                if 'accounts' in accounts_data and len(accounts_data['accounts']) > 0:
                                    account_id = str(accounts_data['accounts'][0].get('id') or accounts_data['accounts'][0].get('uuid', ''))
                                elif 'data' in accounts_data and len(accounts_data['data']) > 0:
                                    account_id = str(accounts_data['data'][0].get('id') or accounts_data['data'][0].get('uuid', ''))
                                elif 'id' in accounts_data:
                                    account_id = str(accounts_data['id'])
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"[Console Login] Could not parse accounts response as JSON: {str(e)}")
                        logger.warning(f"[Console Login] Response text: {accounts_response.text[:500]}")
                else:
                    logger.warning(f"[Console Login] Failed to fetch accounts. Status: {accounts_response.status_code}")
            
            # ========================================================================
            # Step 5: GET /api/console/accounts/switch → Set active account (CRITICAL)
            # ========================================================================
            if account_id:
                logger.info(f"[Console Login] Step 5: Setting active account to ID: {account_id} (CRITICAL STEP)")
                
                switch_url = f"{self.console_base_url}/api/console/accounts/switch"
                switch_params = {'id': account_id}
                switch_headers = {
                    'X-CSRF-Token': console_csrf_token,
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Cache-Control': 'no-cache'
                }
                
                # Session automatically includes cookies from previous steps
                switch_response = self.session.get(
                    switch_url,
                    params=switch_params,
                    headers=switch_headers,
                    timeout=30
                )
                
                logger.info(f"[Console Login] Switch response status: {switch_response.status_code}")
                logger.info(f"[Console Login] Cookies after Step 5: {dict(self.session.cookies)}")
                
                if switch_response.status_code in [200, 302, 303]:
                    logger.info(f"[Console Login] ✅ Account switched successfully to ID: {account_id}")
                    logger.info(f"[Console Login] Session now has account_id set - ready for API calls")
                else:
                    logger.warning(f"[Console Login] Account switch returned status {switch_response.status_code}")
                    logger.warning(f"[Console Login] Response: {switch_response.text[:500]}")
                    logger.warning(f"[Console Login] This may cause 'is_active_account_member' errors")
            else:
                logger.error("[Console Login] ❌ CRITICAL: No account ID available - cannot switch account!")
                logger.error("[Console Login] This will cause 'is_active_account_member' authorization to fail")
                logger.error("[Console Login] Please set console_account_id parameter or ensure accounts API returns valid data")
            
            # ========================================================================
            # Step 6: Authentication complete - cache token and return
            # ========================================================================
            logger.info(f"[Console Login] ✅ Complete authentication workflow finished successfully")
            logger.info(f"[Console Login] Final cookies in session: {dict(self.session.cookies)}")
            logger.info(f"[Console Login] Ready to make authenticated API calls")
            
            self._csrf_token_cache = console_csrf_token
            self.console_csrf_token = console_csrf_token
            return console_csrf_token
            
        except requests.exceptions.Timeout:
            logger.error(f"[Console Login] Login request timed out")
            return None
        except Exception as e:
            logger.error(f"[Console Login] Error during login: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _get_console_headers(self) -> Dict[str, str]:
        """
        Get headers for Console API requests with CRITICAL headers for API access.
        Missing these headers causes HTML redirects instead of JSON responses.
        Note: Cookies are automatically handled by the session object.
        """
        # Try to use provided CSRF token first
        csrf_token = self.console_csrf_token
        
        # If no token provided, try cached token
        if not csrf_token and self._csrf_token_cache:
            logger.info("[Console API] Using cached CSRF token")
            csrf_token = self._csrf_token_cache
        
        # If still no token, try to get one via login
        if not csrf_token and self.console_username and self.console_password:
            logger.info("[Console API] No CSRF token, attempting automatic login")
            csrf_token = self._get_csrf_token_via_login()
            # Update instance variable if we got a token
            if csrf_token:
                self.console_csrf_token = csrf_token
        
        # Log cookie status
        if self.session:
            logger.info(f"[Console API] Session cookies available: {list(self.session.cookies.keys())}")
        
        # CRITICAL: These headers are required for API access
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",  # CRITICAL: Tells server we want JSON
            "X-Requested-With": "XMLHttpRequest",  # CRITICAL: Identifies as AJAX request
            "Cache-Control": "no-cache"
        }

        # Add Referer header (matching Postman format)
        if self.console_base_url:
            headers["Referer"] = f"{self.console_base_url}/login"
        
        # CRITICAL: Only add X-CSRF-Token if we have a valid token (not None)
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
            logger.info(f"[Console API] Using CSRF token: {csrf_token[:20]}...")
        else:
            logger.error("[Console API] ⚠️ CRITICAL: No CSRF token available - request will fail!")
        
        # Add Cookie header explicitly (matching Postman format)
        if self.session and self.session.cookies:
            # Get only the _pos_session cookie
            pos_session_value = self.session.cookies.get('_pos_session')
            if pos_session_value:
                headers["Cookie"] = f"_pos_session={pos_session_value}"
                logger.info(f"[Console API] Adding Cookie header with _pos_session: {pos_session_value[:20]}...")
            else:
                logger.warning("[Console API] ⚠️ _pos_session cookie not found in session")
        else:
            logger.warning("[Console API] ⚠️ No session cookies available - Cookie header will not be sent")

        return headers
    
    def _make_console_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make a request to Console API using authenticated session if available.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            **kwargs: Additional arguments for requests
        
        Returns:
            Response object
        """
        # Use authenticated session if available, otherwise create new request
        if self.session:
            if method.upper() == "GET":
                return self.session.get(url, **kwargs)
            elif method.upper() == "POST":
                return self.session.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        else:
            if method.upper() == "GET":
                return requests.get(url, **kwargs)
            elif method.upper() == "POST":
                return requests.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
    
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
        timestamp = str(int(time.time()))
        payload = {"timestamp": timestamp}
        token = jwt.encode(payload, self.aws_instance_jwt_secret, algorithm='HS256')
        encrypted_token = self._encrypt_token(token, self.aws_instance_jwt_secret)
        return encrypted_token
    
    # ============================================================================
    # CONSOLE API METHODS (Frontend validation + Direct database save)
    # ============================================================================
    
    # def check_subdomain_availability(self, subdomain: str) -> Dict[str, Any]:
    #     """
    #     Check subdomain availability via Console API (frontend validation).
    #     This does NOT save to database, only validates.
        
    #     Endpoint: GET /api/console/subdomain/check
        
    #     Args:
    #         subdomain: The subdomain to check
        
    #     Returns:
    #         Dict with availability status
    #     """
    #     logger.info(f"[Console API] Checking subdomain availability: {subdomain}")
        
    #     if not self.console_base_url:
    #         return {
    #             "success": False,
    #             "error": "Console URL not configured. Set console_base_url parameter."
    #         }
        
    #     # Ensure we have authentication
    #     if not self.session and not self.console_csrf_token:
    #         if self.console_username and self.console_password:
    #             logger.info("[Console API] No session found, attempting to login...")
    #             csrf_token = self._get_csrf_token_via_login()
    #             if csrf_token:
    #                 self.console_csrf_token = csrf_token
    #             else:
    #                 logger.warning("[Console API] Failed to obtain CSRF token via login")
        
    #     try:
    #         url = f"{self.console_base_url}/console/subdomain/check"
    #         headers = self._get_console_headers()
    #         params = {"name": subdomain}
            
    #         logger.info(f"[Console API] Making request to: {url}")
    #         logger.info(f"[Console API] Headers: {headers}")
    #         response = self._make_console_request("GET", url, headers=headers, params=params, timeout=30)
            
    #         # Check if we got HTML instead of JSON
    #         content_type = response.headers.get('Content-Type', '')
    #         logger.info(f"[Console API] Response Content-Type: {content_type}")
    #         logger.info(f"[Console API] Response status: {response.status_code}")
    #         logger.info(f"[Console API] Final URL: {response.url}")
            
    #         if 'text/html' in content_type:
    #             logger.error(f"[Console API] ERROR: Got HTML instead of JSON")
    #             if 'login' in response.url.lower():
    #                 logger.error(f"[Console API] Redirected to login page - authentication failed")
    #                 return {
    #                     "success": False,
    #                     "error": "Authentication failed - redirected to login page",
    #                     "subdomain": subdomain,
    #                     "api": "console"
    #                 }
    #             else:
    #                 logger.error(f"[Console API] Got HTML response - check endpoint URL or headers")
    #                 return {
    #                     "success": False,
    #                     "error": "Received HTML instead of JSON - check endpoint or headers",
    #                     "response_sample": response.text[:200],
    #                     "subdomain": subdomain,
    #                     "api": "console"
    #                 }
            
    #         if response.status_code == 200:
    #             if not response.text or not response.text.strip():
    #                 logger.warning(f"[Console API] Empty response from subdomain check endpoint")
    #                 return {
    #                     "success": False,
    #                     "error": "Empty response from console API",
    #                     "subdomain": subdomain,
    #                     "api": "console"
    #                 }
                
    #             try:
    #                 result = response.json()
    #                 is_available = result.get("available", False)
                    
    #                 logger.info(f"[Console API] Subdomain '{subdomain}' availability: {is_available}")
    #                 return {
    #                     "success": True,
    #                     "available": is_available,
    #                     "subdomain": subdomain,
    #                     "result": result,
    #                     "message": f"Subdomain '{subdomain}' is {'available' if is_available else 'unavailable'}",
    #                     "api": "console"
    #                 }
    #             except json.JSONDecodeError as json_err:
    #                 logger.error(f"[Console API] Invalid JSON response: {response.text[:200]}")
    #                 return {
    #                     "success": False,
    #                     "error": f"Invalid JSON response: {str(json_err)}",
    #                     "response_text": response.text[:500],
    #                     "subdomain": subdomain,
    #                     "api": "console"
    #                 }
    #         else:
    #             logger.warning(f"[Console API] Check failed. Status: {response.status_code}")
    #             return {
    #                 "success": False,
    #                 "status_code": response.status_code,
    #                 "error": response.text[:500] if response.text else "No response body",
    #                 "subdomain": subdomain,
    #                 "api": "console"
    #             }
                
    #     except requests.exceptions.Timeout:
    #         return {"success": False, "error": "Request timed out after 30 seconds", "api": "console"}
    #     except Exception as e:
    #         logger.error(f"[Console API] Check error: {str(e)}")
    #         import traceback
    #         logger.error(f"[Console API] Traceback: {traceback.format_exc()}")
    #         return {
    #             "success": False,
    #             "error": str(e),
    #             "subdomain": subdomain,
    #             "api": "console"
    #         }
    
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
        availability_check = self.validate_subdomain(subdomain)
        
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
            # CRITICAL: Use /api/console/instances not /console
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
                        # "environment": environment,
                        "environment": "Staging",
                        "instance_data_centre": instance_data_centre,
                        "instance_billing_plan": instance_billing_plan,
                        "status": "Initialising"
                    },
                    "pay_on_invoice": pay_on_invoice
                }
            }
            
            if image:
                payload["payload"]["properties"]["image"] = image
            
            logger.info(f"[Console API] Sending create request to: {url}")
            logger.info(f"[Console API] Headers: {headers}")
            logger.info(f"[Console API] Payload: {json.dumps(payload, indent=2)}")
            
            response = self._make_console_request("POST", url, headers=headers, json=payload, timeout=60)
            
            # Check if we got HTML instead of JSON
            content_type = response.headers.get('Content-Type', '')
            logger.info(f"[Console API] Response Content-Type: {content_type}")
            logger.info(f"[Console API] Response status: {response.status_code}")
            logger.info(f"[Console API] Final URL: {response.url}")
            
            if 'text/html' in content_type:
                logger.error(f"[Console API] ERROR: Got HTML instead of JSON")
                if 'login' in response.url.lower():
                    return {
                        "success": False,
                        "error": "Authentication failed - redirected to login page",
                        "status_code": response.status_code,
                        "api": "console"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Received HTML instead of JSON - check endpoint URL or headers",
                        "response_sample": response.text[:200],
                        "status_code": response.status_code,
                        "api": "console"
                    }
            
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
                except json.JSONDecodeError as json_err:
                    logger.error(f"[Console API] Invalid JSON response: {response.text[:200]}")
                    return {
                        "success": False,
                        "error": f"Invalid JSON response from Console API: {str(json_err)}",
                        "status_code": response.status_code,
                        "api": "console"
                    }
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errors", [{}])[0].get("message", "Instance creation failed")
                except:
                    error_msg = "Instance creation failed"
                    error_data = response.text
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
                    "error": "Unauthorized. Check credentials or CSRF token.",
                    "status_code": 401,
                    "api": "console"
                }
            else:
                logger.warning(f"[Console API] Creation failed. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:500] if response.text else "No response body",
                    "subdomain": subdomain,
                    "api": "console"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 60 seconds", "api": "console"}
        except Exception as e:
            logger.error(f"[Console API] Creation error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
        """Validate subdomain availability via AWS Gateway (step function validation)."""
        logger.info(f"[AWS Gateway] Validating subdomain: {subdomain}")
        
        try:
            auth_token = self._create_authorization_header()
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
        
        required_fields = ["subdomain", "pos_billing_plan_id", "pos_data_centre_id"]
        missing_fields = [field for field in required_fields if field not in instance_data]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }
        
        subdomain = instance_data["subdomain"]
        
        logger.info(f"[AWS Gateway] Step 1: Validating subdomain '{subdomain}'")
        validation_result = self.validate_subdomain(subdomain)
        
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
            auth_token = self._create_authorization_header()
            endpoint = f"{self.aws_create_instance_url}/Staging/create-instance"
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_token
            }
            
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
                    "pos_billing_plan_id": instance_data["pos_billing_plan_id"],
                    "pos_data_centre_id": instance_data["pos_data_centre_id"],
                    "instance_params": {
                        "name": subdomain,
                        "tag_list": ",".join(instance_data.get("tags", []))
                    },
                    "created_by": instance_data.get("created_by", ""),
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
        subdomain: str,
        environment: str,
        instance_data_centre: str,
        instance_billing_plan: str,
        pos_billing_plan_id: str,
        pos_data_centre_id: str,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = "",
        pay_on_invoice: bool = False,
        domain_ids: Optional[List[str]] = None,
        image: Optional[str] = None,
        is_duplication: bool = False,
        request_full_url: str = "",
        request_ip: str = "",
        request_user_id: str = "",
        partner_id: str = "11"
    ) -> Dict[str, Any]:
        """
        Complete instance creation workflow:
        1. Check subdomain availability
        2. Save to database via Console API (create_instance_console) - CRUCIAL STEP
        3. Update via AWS Gateway step function (create_instance)
        
        The Console API creates the initial database record which is then
        updated by the step function.
        
        Args:
            name: Instance name
            subdomain: Instance subdomain
            environment: 'Staging' or 'Production'
            instance_data_centre: Data centre ID (for Console API)
            instance_billing_plan: Billing plan ID (for Console API)
            pos_billing_plan_id: POS billing plan ID (for AWS Gateway)
            pos_data_centre_id: POS data centre ID (for AWS Gateway)
            tags: Optional list of tags
            created_by: User who created the instance
            pay_on_invoice: Payment method
            domain_ids: Optional domain IDs
            image: Optional image URL or base64
            is_duplication: Whether this is a duplication
            request_full_url: Request URL for metadata
            request_ip: Request IP for metadata
            request_user_id: User ID for metadata
            partner_id: Partner ID
        
        Returns:
            Dict with complete workflow result
        """
        logger.info(f"[COMPLETE WORKFLOW] Starting for subdomain: {subdomain}")
        
        workflow_results = {"subdomain": subdomain, "steps": {}}
        
        # Step 1: Check subdomain availability
        logger.info(f"[COMPLETE WORKFLOW] Step 1: Checking subdomain availability")
        availability_check = self.validate_subdomain(subdomain)
        workflow_results["steps"]["1_availability_check"] = availability_check
        
        if not availability_check.get("success") or not availability_check.get("available"):
            return {
                "success": False,
                "error": f"Subdomain '{subdomain}' is not available",
                "workflow_results": workflow_results
            }
        
        # Step 2: Create database record via Console API
        logger.info(f"[COMPLETE WORKFLOW] Step 2: Creating database record via Console API")
        console_creation = self.create_instance_console(
            name=name,
            subdomain=subdomain,
            environment=environment,
            instance_data_centre=instance_data_centre,
            instance_billing_plan=instance_billing_plan,
            tags=tags,
            pay_on_invoice=pay_on_invoice,
            domain_ids=domain_ids,
            image=image
        )
        workflow_results["steps"]["2_console_creation"] = console_creation
        
        if not console_creation.get("success"):
            return {
                "success": False,
                "error": "Failed to create database record via Console API",
                "workflow_results": workflow_results
            }
        
        logger.info(f"[COMPLETE WORKFLOW] Database record created successfully")
        
        # Step 3: Update via AWS Gateway
        logger.info(f"[COMPLETE WORKFLOW] Step 3: Updating via AWS Gateway")
        
        gateway_instance_data = {
            "subdomain": subdomain,
            "pos_billing_plan_id": pos_billing_plan_id,
            "pos_data_centre_id": pos_data_centre_id,
            "tags": tags or [],
            "created_by": created_by,
            "is_duplication": is_duplication,
            "request_full_url": request_full_url,
            "request_ip": request_ip,
            "request_user_id": request_user_id,
            "partner_id": partner_id
        }
        
        gateway_result = self.create_instance(gateway_instance_data, environment)
        workflow_results["steps"]["3_gateway_update"] = gateway_result
        
        return {
            "success": True,
            "subdomain": subdomain,
            "message": f"Instance '{subdomain}' created successfully",
            "workflow_results": workflow_results,
            "database_saved": True,
            "step_function_updated": gateway_result.get("success", False)
        }
    
    # ============================================================================
    # LANGCHAIN TOOLS
    # ============================================================================
    
    def get_langchain_tools(self) -> List:
        """Convert Instance methods to LangChain tools."""
        from langchain_core.tools import tool
        
        tools = []
        
        @tool
        # def check_subdomain_availability(subdomain: str) -> str:
        #     """Check subdomain availability via Console API."""
        #     result = self.check_subdomain_availability(subdomain)
        #     return json.dumps(result, indent=2)
        
        @tool
        def create_instance_console(instance_data: str) -> str:
            """Create instance via Console API (direct database save)."""
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
        def create_instance_complete_workflow(instance_data: str, environment: str = "production") -> str:
            """Complete instance creation workflow (RECOMMENDED METHOD)."""
            try:
                data = json.loads(instance_data) if isinstance(instance_data, str) else instance_data
                result = self.create_instance_complete_workflow(
                    name=data["name"],
                    subdomain=data["subdomain"],
                    environment=data["environment"],
                    instance_data_centre=data["instance_data_centre"],
                    instance_billing_plan=data["instance_billing_plan"],
                    pos_billing_plan_id=data["pos_billing_plan_id"],
                    pos_data_centre_id=data["pos_data_centre_id"],
                    tags=data.get("tags"),
                    created_by=data.get("created_by", ""),
                    pay_on_invoice=data.get("pay_on_invoice", False),
                    domain_ids=data.get("domain_ids"),
                    image=data.get("image"),
                    is_duplication=data.get("is_duplication", False),
                    request_full_url=data.get("request_full_url", ""),
                    request_ip=data.get("request_ip", ""),
                    request_user_id=data.get("request_user_id", ""),
                    partner_id=data.get("partner_id", "11")
                )
                return json.dumps(result, indent=2)
            except (json.JSONDecodeError, KeyError) as e:
                return json.dumps({"success": False, "error": f"Invalid input: {str(e)}"}, indent=2)
        
        tools.extend([
            # check_subdomain_availability,
            create_instance_console,
            validate_subdomain,
            create_instance,
            create_instance_complete_workflow
        ])
        
        return tools