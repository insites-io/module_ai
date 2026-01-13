import requests
import json
import logging
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Logger is configured in main.py - just get the logger here
logger = logging.getLogger(__name__)

class ContactData(BaseModel):
    """Schema for contact data."""
    contact_data: Dict[str, Any] = Field(description="Contact data to save")

class ContactUUID(BaseModel):
    """Schema for contact UUID."""
    contact_uuid: str = Field(description="UUID of the contact")

class ContactsParams(BaseModel):
    """Schema for get_contacts parameters."""
    page: Optional[int] = Field(default=1, description="Page number for pagination")
    size: Optional[int] = Field(default=10, description="Number of contacts per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    search_by: Optional[str] = Field(default=None, description="Field to search in")
    keyword: Optional[str] = Field(default=None, description="Search keyword")
    sort_order: Optional[str] = Field(default="ASC", description="Sort order: ASC or DESC")

class CompaniesParams(BaseModel):
    """Schema for get_companies parameters."""
    page: Optional[int] = Field(default=1, description="Page number for pagination")
    size: Optional[int] = Field(default=10, description="Number of companies per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    search_by: Optional[str] = Field(default=None, description="Field to search in")
    keyword: Optional[str] = Field(default=None, description="Search keyword")
    sort_order: Optional[str] = Field(default="ASC", description="Sort order: ASC or DESC")

class CRMTools:
    """CRM Tools class that provides all CRM-related functionality."""
    
    def __init__(self, instance_url: str, instance_api_key: str):
        self.instance_url = instance_url
        self.instance_api_key = instance_api_key
        self.headers = {
            "Authorization": instance_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def _fetch_api_data(self, endpoint: str) -> Dict[str, Any]:
        """Utility method to fetch data from CRM API."""
        if not self.instance_url or not self.instance_api_key:
            return {
                "success": False,
                "error": "Instance URL and API key not configured"
            }

        url = f"{self.instance_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            # Check if response is HTML instead of JSON
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type or response.text.strip().startswith('<'):
                logger.warning(f"Received HTML response from endpoint: {endpoint}")
                return {
                    "success": False,
                    "error": f"Received HTML response from endpoint: {endpoint}",
                    "status_code": response.status_code,
                    "content_type": content_type
                }
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    return {"success": True, "result": result}
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from endpoint: {endpoint}")
                    return {
                        "success": False,
                        "error": f"Invalid JSON response from endpoint: {endpoint}",
                        "status_code": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "content_type": content_type
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_query_string(self, params: Dict[str, Any]) -> str:
        """Build query string from parameters, excluding None values."""
        query_parts = []
        for key, value in params.items():
            if value is not None:
                query_parts.append(f"{key}={value}")
        return "&".join(query_parts) if query_parts else ""
    
    def get_contacts(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get contacts from the CRM system with pagination and search support.
        
        Args:
            params: Dictionary with optional keys:
                - page: Page number (default: 1)
                - size: Number of contacts per page (default: 10)
                - sort_by: Field to sort by (e.g., 'last_name', 'first_name')
                - search_by: Field to search in (e.g., 'first_name', 'last_name', 'email')
                - keyword: Search keyword
                - sort_order: 'ASC' or 'DESC' (default: 'ASC')
        """
        logger.info(f"Getting contacts with params: {params}")
        
        # Set defaults
        if params is None:
            params = {}
        
        query_params = {
            "page": params.get("page", 1),
            "size": params.get("size", 10),
        }
        
        # Add optional parameters if provided
        if "sort_by" in params and params["sort_by"]:
            query_params["sort_by"] = params["sort_by"]
        if "search_by" in params and params["search_by"]:
            query_params["search_by"] = params["search_by"]
        if "keyword" in params and params["keyword"]:
            query_params["keyword"] = params["keyword"]
        if "sort_order" in params and params["sort_order"]:
            query_params["sort_order"] = params["sort_order"]
        
        # Build query string
        query_string = self._build_query_string(query_params)
        endpoint = f"/crm/api/v2/contacts?{query_string}"
        
        logger.info(f"Fetching contacts from: {endpoint}")
        result = self._fetch_api_data(endpoint)
        logger.info(f"Retrieved contacts: {result.get('success', False)}")
        return result

    def get_companies(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get companies from the CRM system with pagination and search support.
        
        Args:
            params: Dictionary with optional keys:
                - page: Page number (default: 1)
                - size: Number of companies per page (default: 10)
                - sort_by: Field to sort by (e.g., 'company_name')
                - search_by: Field to search in (e.g., 'company_name')
                - keyword: Search keyword
                - sort_order: 'ASC' or 'DESC' (default: 'ASC')
        """
        logger.info(f"Getting companies with params: {params}")
        
        # Set defaults
        if params is None:
            params = {}
        
        query_params = {
            "page": params.get("page", 1),
            "size": params.get("size", 10),
        }
        
        # Add optional parameters if provided
        if "sort_by" in params and params["sort_by"]:
            query_params["sort_by"] = params["sort_by"]
        if "search_by" in params and params["search_by"]:
            query_params["search_by"] = params["search_by"]
        if "keyword" in params and params["keyword"]:
            query_params["keyword"] = params["keyword"]
        if "sort_order" in params and params["sort_order"]:
            query_params["sort_order"] = params["sort_order"]
        
        # Build query string
        query_string = self._build_query_string(query_params)
        endpoint = f"/crm/api/v2/companies?{query_string}"
        
        logger.info(f"Fetching companies from: {endpoint}")
        result = self._fetch_api_data(endpoint)
        logger.info(f"Retrieved companies: {result.get('success', False)}")
        return result

    def get_contact_relationships(self) -> Dict[str, Any]:
        """Get contact relationships from the CRM system."""
        logger.info("Getting contact relationships...")
        result = self._fetch_api_data("/crm/api/v2/contacts/relationships")
        logger.info(f"Retrieved contact relationships: {result.get('success', False)}")
        return result

    def get_contact_addresses(self) -> Dict[str, Any]:
        """Get contact addresses from the CRM system."""
        logger.info("Getting contact addresses...")
        result = self._fetch_api_data("/crm/api/v2/contacts/addresses")
        logger.info(f"Retrieved contact addresses: {result.get('success', False)}")
        return result

    def get_company_relationships(self) -> Dict[str, Any]:
        """Get company relationships from the CRM system."""
        logger.info("Getting company relationships...")
        result = self._fetch_api_data("/crm/api/v2/companies/relationships")
        logger.info(f"Retrieved company relationships: {result.get('success', False)}")
        return result

    def get_company_addresses(self) -> Dict[str, Any]:
        """Get company addresses from the CRM system."""
        logger.info("Getting company addresses...")
        result = self._fetch_api_data("/crm/api/v2/companies/addresses")
        logger.info(f"Retrieved company addresses: {result.get('success', False)}")
        return result

    def get_system_fields(self) -> Dict[str, Any]:
        """Get system fields from the CRM system."""
        logger.info("Getting system fields...")
        result = self._fetch_api_data("/crm/api/v2/system-fields")
        logger.info(f"Retrieved system fields: {result.get('success', False)}")
        return result

    def get_contact_system_fields(self) -> Dict[str, Any]:
        """Get contact custom fields from the CRM system."""
        logger.info("Getting contact system fields...")
        result = self._fetch_api_data("/crm/api/v2/custom-fields/contacts")
        logger.info(f"Retrieved contact system fields: {result.get('success', False)}")
        return result

    def get_company_system_fields(self) -> Dict[str, Any]:
        """Get company custom fields from the CRM system."""
        logger.info("Getting company system fields...")
        result = self._fetch_api_data("/crm/api/v2/custom-fields/companies")
        logger.info(f"Retrieved company system fields: {result.get('success', False)}")
        return result

    def save_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new contact or update an existing contact."""
        logger.info(f"Saving contact with data: {contact_data}")
        
        if not self.instance_url or not self.instance_api_key:
            return {
                "success": False,
                "error": "Instance URL and API key not configured"
            }

        url = f"{self.instance_url}/crm/api/v2/contacts"
        
        try:
            # Determine if this is create or update
            if "uuid" in contact_data:
                # Update existing contact
                contact_uuid = contact_data["uuid"]
                url = f"{self.instance_url}/crm/api/v2/contacts/{contact_uuid}"
                response = requests.put(url, headers=self.headers, json=contact_data, timeout=30)
                logger.info(f"Updating contact with UUID: {contact_uuid}")
            else:
                # Create new contact
                response = requests.post(url, headers=self.headers, json=contact_data, timeout=30)
                logger.info("Creating new contact")
            
            if response.status_code in [200, 201]:
                try:
                    contact_result = response.json()
                    logger.info(f"Contact saved successfully")
                    return {
                        "success": True,
                        "result": contact_result,
                        "message": "Contact saved successfully" if response.status_code == 201 else "Contact updated successfully"
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response when saving contact")
                    return {
                        "success": False,
                        "error": "Invalid JSON response when saving contact",
                        "status_code": response.status_code
                    }
            else:
                logger.warning(f"Failed to save contact. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds"}
        except Exception as e:
            logger.error(f"Error saving contact: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new company."""
        logger.info(f"Creating company with data: {company_data}")
        
        if not self.instance_url or not self.instance_api_key:
            return {
                "success": False,
                "error": "Instance URL and API key not configured"
            }

        url = f"{self.instance_url}/crm/api/v2/companies"
        
        try:
            response = requests.post(url, headers=self.headers, json=company_data, timeout=30)
            
            if response.status_code in [200, 201]:
                try:
                    company_result = response.json()
                    logger.info(f"Company created successfully")
                    return {
                        "success": True,
                        "result": company_result,
                        "message": "Company created successfully"
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response when creating company",
                        "status_code": response.status_code
                    }
            else:
                logger.warning(f"Failed to create company. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds"}
        except Exception as e:
            logger.error(f"Error creating company: {str(e)}")
            return {"success": False, "error": str(e)}

    def update_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing company."""
        logger.info(f"Updating company with data: {company_data}")
        
        company_uuid = company_data.get("uuid")
        if not company_uuid:
            return {"success": False, "error": "Company UUID is required for updates"}
        
        if not self.instance_url or not self.instance_api_key:
            return {
                "success": False,
                "error": "Instance URL and API key not configured"
            }

        url = f"{self.instance_url}/crm/api/v2/companies/{company_uuid}"
        
        # Remove uuid from payload (only for update body)
        payload = {k: v for k, v in company_data.items() if k != "uuid"}
        
        try:
            response = requests.put(url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                try:
                    company_result = response.json()
                    logger.info(f"Company updated successfully")
                    return {
                        "success": True,
                        "result": company_result,
                        "message": "Company updated successfully"
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response when updating company",
                        "status_code": response.status_code
                    }
            else:
                logger.warning(f"Failed to update company. Status: {response.status_code}")
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out after 30 seconds"}
        except Exception as e:
            logger.error(f"Error updating company: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_contact_by_uuid(self, contact_uuid: str) -> Dict[str, Any]:
        """Get a specific contact by UUID."""
        logger.info(f"Getting contact by UUID: {contact_uuid}")
        
        if not self.instance_url or not self.instance_api_key:
            return {
                "success": False,
                "error": "Instance URL and API key not configured"
            }

        url = f"{self.instance_url}/crm/api/v2/contacts/{contact_uuid}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                try:
                    contact_data = response.json()
                    return {
                        "success": True,
                        "contact": contact_data,
                        "message": "Contact retrieved successfully"
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON response",
                        "status_code": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_langchain_tools(self) -> List:
        """Convert CRM methods to LangChain tools."""
        tools = []
        
        # Create tool functions that capture self in closure
        @tool
        def get_contacts(params: str = "{}") -> str:
            """Get contacts from the CRM system with pagination and search.
            
            Args:
                params: JSON string with optional parameters:
                    - page: Page number (default: 1)
                    - size: Number of contacts per page (default: 10)
                    - sort_by: Field to sort by (e.g., 'last_name', 'first_name')
                    - search_by: Field to search in (e.g., 'first_name', 'last_name', 'email')
                    - keyword: Search keyword
                    - sort_order: 'ASC' or 'DESC' (default: 'ASC')
            
            Examples:
                - Get page 2: params='{"page": 2, "size": 10}'
                - Search by name: params='{"search_by": "first_name", "keyword": "John"}'
                - Sort by last name descending: params='{"sort_by": "last_name", "sort_order": "DESC"}'
            """
            try:
                param_dict = json.loads(params) if isinstance(params, str) else params
                result = self.get_contacts(param_dict)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def get_companies(params: str = "{}") -> str:
            """Get companies from the CRM system with pagination and search.
            
            Args:
                params: JSON string with optional parameters:
                    - page: Page number (default: 1)
                    - size: Number of companies per page (default: 10)
                    - sort_by: Field to sort by (e.g., 'company_name')
                    - search_by: Field to search in (e.g., 'company_name')
                    - keyword: Search keyword
                    - sort_order: 'ASC' or 'DESC' (default: 'ASC')
            """
            try:
                param_dict = json.loads(params) if isinstance(params, str) else params
                result = self.get_companies(param_dict)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def get_contact_relationships() -> str:
            """Get contact relationships from the CRM system."""
            result = self.get_contact_relationships()
            return json.dumps(result, indent=2)
        
        @tool
        def get_contact_addresses() -> str:
            """Get contact addresses from the CRM system."""
            result = self.get_contact_addresses()
            return json.dumps(result, indent=2)
        
        @tool
        def get_company_relationships() -> str:
            """Get company relationships from the CRM system."""
            result = self.get_company_relationships()
            return json.dumps(result, indent=2)
        
        @tool
        def get_company_addresses() -> str:
            """Get company addresses from the CRM system."""
            result = self.get_company_addresses()
            return json.dumps(result, indent=2)
        
        @tool
        def get_system_fields() -> str:
            """Get system fields from the CRM system."""
            result = self.get_system_fields()
            return json.dumps(result, indent=2)
        
        @tool
        def get_contact_system_fields() -> str:
            """Get contact custom fields from the CRM system."""
            result = self.get_contact_system_fields()
            return json.dumps(result, indent=2)
        
        @tool
        def get_company_system_fields() -> str:
            """Get company custom fields from the CRM system."""
            result = self.get_company_system_fields()
            return json.dumps(result, indent=2)
        
        @tool
        def save_contact(contact_data: str) -> str:
            """Save or update a contact in the CRM system.
            
            Args:
                contact_data: JSON string containing contact information
            """
            try:
                data = json.loads(contact_data) if isinstance(contact_data, str) else contact_data
                result = self.save_contact(data)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def create_company(company_data: str) -> str:
            """Create a new company in the CRM system.
            
            Args:
                company_data: JSON string containing company information
            """
            try:
                data = json.loads(company_data) if isinstance(company_data, str) else company_data
                result = self.create_company(data)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def update_company(company_data: str) -> str:
            """Update an existing company in the CRM system.
            
            Args:
                company_data: JSON string containing company information (must include uuid)
            """
            try:
                data = json.loads(company_data) if isinstance(company_data, str) else company_data
                result = self.update_company(data)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError as e:
                return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"}, indent=2)
        
        @tool
        def get_contact_by_uuid(contact_uuid: str) -> str:
            """Get a specific contact by their UUID.
            
            Args:
                contact_uuid: The UUID of the contact to retrieve
            """
            result = self.get_contact_by_uuid(contact_uuid)
            return json.dumps(result, indent=2)
        
        # Add all tools to the list
        tools.extend([
            get_contacts,
            get_companies,
            get_contact_relationships,
            get_contact_addresses,
            get_company_relationships,
            get_company_addresses,
            get_system_fields,
            get_contact_system_fields,
            get_company_system_fields,
            save_contact,
            create_company,
            update_company,
            get_contact_by_uuid
        ])
        
        return tools