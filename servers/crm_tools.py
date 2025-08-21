import requests
import json
import logging
from typing import Dict, Any, List
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContactData(BaseModel):
    """Schema for contact data."""
    contact_data: Dict[str, Any] = Field(description="Contact data to save")

class ContactUUID(BaseModel):
    """Schema for contact UUID."""
    contact_uuid: str = Field(description="UUID of the contact")

class AddressData(BaseModel):
    """Schema for address data."""
    address_data: Dict[str, Any] = Field(description="Address data to save")

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
    
    def get_contacts(self) -> Dict[str, Any]:
        """Get all contacts from the CRM system."""
        logger.info("Getting all contacts...")
        result = self._fetch_api_data("/crm/api/v2/contacts?page=1&size=10")
        logger.info(f"Retrieved contacts: {result.get('success', False)}")
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

    def get_companies(self) -> Dict[str, Any]:
        """Get all companies from the CRM system."""
        logger.info("Getting all companies...")
        result = self._fetch_api_data("/crm/api/v2/companies")
        logger.info(f"Retrieved companies: {result.get('success', False)}")
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
        def get_contacts() -> str:
            """Get all contacts from the CRM system."""
            result = self.get_contacts()
            return json.dumps(result, indent=2)
        
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
        def get_companies() -> str:
            """Get all companies from the CRM system."""
            result = self.get_companies()
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
                # Parse the JSON string to dict
                data = json.loads(contact_data) if isinstance(contact_data, str) else contact_data
                result = self.save_contact(data)
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
            get_contact_relationships,
            get_contact_addresses,
            get_companies,
            get_company_relationships,
            get_company_addresses,
            get_system_fields,
            get_contact_system_fields,
            get_company_system_fields,
            save_contact,
            get_contact_by_uuid
        ])
        
        return tools