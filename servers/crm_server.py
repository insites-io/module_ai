import asyncio
import requests
import argparse
import sys
import os
import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
import json # Added for json.JSONDecodeError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add a custom handler to also log to stderr for better visibility
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

# Argument Parsing with defaults for Claude Desktop usage
def parse_arguments():
    parser = argparse.ArgumentParser(description='MCP CRM Server with dynamic instance configuration')
    parser.add_argument('--instance-url', type=str, required=True, help='Instance URL for external API calls')
    parser.add_argument('--instance-api-key', type=str, required=True, help='Instance API key for authentication')
    return parser.parse_args()

# Parse arguments - this is what the MCP library expects
try:
    args = parse_arguments()
    INSTANCE_URL = args.instance_url
    INSTANCE_API_KEY = args.instance_api_key
except SystemExit as e:
    # If --help or --version is used, let it exit normally
    if "--help" in sys.argv or "--version" in sys.argv:
        sys.exit(e.code)
    # If no arguments provided (like when imported), use environment variables or defaults
    INSTANCE_URL = os.getenv("CRM_INSTANCE_URL")
    INSTANCE_API_KEY = os.getenv("CRM_INSTANCE_API_KEY")

# FastMCP Initialization - lazy load to avoid hanging during import
_mcp_instance = None

def get_mcp():
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = FastMCP("crm-server")
    return _mcp_instance

# Create a proxy object that delegates to the actual FastMCP instance
class MCPProxy:
    def tool(self, *args, **kwargs):
        return get_mcp().tool(*args, **kwargs)
    
    def run(self, *args, **kwargs):
        return get_mcp().run(*args, **kwargs)

mcp = MCPProxy()

# Utility: API Request
def fetch_api_data(endpoint: str) -> Dict[str, Any]:
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables or provide --instance-url and --instance-api-key arguments."
        }

    url = f"{INSTANCE_URL}{endpoint}"
    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)  # Add timeout
        
        # Check if response is HTML instead of JSON
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or response.text.strip().startswith('<'):
            logger.warning(f"Received HTML response instead of JSON from endpoint: {endpoint}")
            return {
                "success": False,
                "error": f"Received HTML response instead of JSON from endpoint: {endpoint}",
                "status_code": response.status_code,
                "content_type": content_type,
                "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
            }
        
        if response.status_code == 200:
            try:
                result = response.json()
                return {"success": True, "result": result}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from endpoint: {endpoint}. Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response from endpoint: {endpoint}",
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
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

# MCP Tools
@mcp.tool()
def get_contacts() -> Dict[str, Any]:
    """
    Get all contacts from the CRM system.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): Whether the operation was successful
            - result (dict): The contacts data if successful
            - error (str): Error message if unsuccessful
            - status_code (int): HTTP status code from the API
    """
    logger.info("Calling get_contacts tool...")
    result = fetch_api_data("/crm/api/v2/contacts")
    logger.info(f"get_contacts tool finished. Result: {result}")
    return result

@mcp.tool()
def get_contact_relationships() -> Dict[str, Any]:
    """
    Get contact relationships from the CRM system.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): Whether the operation was successful
            - result (dict): The contact relationships data if successful
            - error (str): Error message if unsuccessful
            - status_code (int): HTTP status code from the API
    """
    logger.info("Calling get_contact_relationships tool...")
    result = fetch_api_data("/crm/api/v2/contacts/relationships")
    logger.info(f"get_contact_relationships tool finished. Result: {result}")
    return result

@mcp.tool()
def get_contact_addresses() -> Dict[str, Any]:
    """
    Get contact addresses from the CRM system.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): Whether the operation was successful
            - result (dict): The contact addresses data if successful
            - error (str): Error message if unsuccessful
            - status_code (int): HTTP status code from the API
    """
    logger.info("Calling get_contact_addresses tool...")
    result = fetch_api_data("/crm/api/v2/contacts/addresses")
    logger.info(f"get_contact_addresses tool finished. Result: {result}")
    return result

@mcp.tool()
def get_companies() -> Dict[str, Any]:
    """
    Get all companies from the CRM system.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): Whether the operation was successful
            - result (dict): The companies data if successful
            - error (str): Error message if unsuccessful
            - status_code (int): HTTP status code from the API
    """
    logger.info("Calling get_companies tool...")
    result = fetch_api_data("/crm/api/v2/companies")
    logger.info(f"get_companies tool finished. Result: {result}")
    return result

@mcp.tool()
def get_company_relationships() -> Dict[str, Any]:
    logger.info("Calling get_company_relationships tool...")
    result = fetch_api_data("/crm/api/v2/companies/relationships")
    logger.info(f"get_company_relationships tool finished. Result: {result}")
    return result

@mcp.tool()
def get_company_addresses() -> Dict[str, Any]:
    logger.info("Calling get_company_addresses tool...")
    result = fetch_api_data("/crm/api/v2/companies/addresses")
    logger.info(f"get_company_addresses tool finished. Result: {result}")
    return result

@mcp.tool()
def get_system_fields() -> Dict[str, Any]:
    logger.info("Calling get_system_fields tool...")
    result = fetch_api_data("/crm/api/v2/system-fields")
    logger.info(f"get_system_fields tool finished. Result: {result}")
    return result

@mcp.tool()
def get_contact_sytem_fields() -> Dict[str, Any]:
    logger.info("Calling get_contact_sytem_fields tool...")
    result = fetch_api_data("/crm/api/v2/custom-fields/contacts")
    logger.info(f"get_contact_sytem_fields tool finished. Result: {result}")
    return result

@mcp.tool()
def get_company_sytem_fields() -> Dict[str, Any]:
    logger.info("Calling get_company_sytem_fields tool...")
    result = fetch_api_data("/crm/api/v2/custom-fields/companies")
    logger.info(f"get_company_sytem_fields tool finished. Result: {result}")
    return result

@mcp.tool()
def get_contact_addresses_by_uuid(contact_uuid: str) -> Dict[str, Any]:
    """
    Get all addresses for a specific contact by their UUID.
    
    Args:
        contact_uuid: The UUID of the contact to get addresses for
    
    Returns:
        Dictionary with contact addresses or error information
    """
    logger.info(f"Calling get_contact_addresses_by_uuid tool with contact UUID: {contact_uuid}")
    
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        logger.error("Instance URL and API key not configured for get_contact_addresses_by_uuid")
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables or provide --instance-url and --instance-api-key arguments."
        }

    # First verify the contact exists
    contact_check = get_contact_by_uuid(contact_uuid)
    if not contact_check["success"]:
        logger.warning(f"Contact with UUID {contact_uuid} does not exist")
        return {
            "success": False,
            "error": f"Contact with UUID {contact_uuid} does not exist",
            "contact_check_error": contact_check.get("error")
        }

    # Get addresses for the contact
    url = f"{INSTANCE_URL}/crm/api/v2/contacts/addresses/{contact_uuid}"
    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        logger.info(f"get_contact_addresses_by_uuid tool finished. Response status: {response.status_code}")
        
        # Check if response is HTML instead of JSON
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or response.text.strip().startswith('<'):
            logger.warning(f"Received HTML response instead of JSON for contact addresses UUID: {contact_uuid}")
            return {
                "success": False,
                "error": f"Received HTML response instead of JSON for contact addresses UUID: {contact_uuid}",
                "status_code": response.status_code,
                "content_type": content_type,
                "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
            }
        
        if response.status_code == 200:
            try:
                addresses_data = response.json()
                logger.info(f"Retrieved {len(addresses_data.get('data', []))} addresses for contact UUID: {contact_uuid}")
                return {
                    "success": True,
                    "contact_uuid": contact_uuid,
                    "addresses": addresses_data,
                    "message": f"Retrieved addresses for contact {contact_uuid}"
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response for contact addresses UUID: {contact_uuid}. Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response for contact addresses UUID: {contact_uuid}",
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }
        else:
            logger.warning(f"Failed to retrieve addresses for contact UUID {contact_uuid}. Status: {response.status_code}, Error: {response.text}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "content_type": content_type
            }
    except requests.exceptions.Timeout:
        logger.warning(f"Request timed out for get_contact_addresses_by_uuid for contact UUID: {contact_uuid}")
        return {"success": False, "error": "Request timed out after 30 seconds"}
    except Exception as e:
        logger.error(f"Error in get_contact_addresses_by_uuid for contact UUID {contact_uuid}: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_contact_by_uuid(contact_uuid: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific contact by their UUID.
    
    Args:
        contact_uuid: The UUID of the contact to retrieve
    
    Returns:
        Dictionary with contact details or error information
    """
    logger.info(f"Calling get_contact_by_uuid tool with UUID: {contact_uuid}")
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        logger.error("Instance URL and API key not configured for get_contact_by_uuid")
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables or provide --instance-url and --instance-api-key arguments."
        }

    url = f"{INSTANCE_URL}/crm/api/v2/contacts/{contact_uuid}"
    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        logger.info(f"get_contact_by_uuid tool finished. Response status: {response.status_code}")
        
        # Check if response is HTML instead of JSON
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or response.text.strip().startswith('<'):
            logger.warning(f"Received HTML response instead of JSON for contact UUID: {contact_uuid}")
            return {
                "success": False,
                "error": f"Received HTML response instead of JSON for contact UUID: {contact_uuid}",
                "status_code": response.status_code,
                "content_type": content_type,
                "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
            }
        
        if response.status_code == 200:
            try:
                contact_data = response.json()
                logger.info(f"Contact retrieved successfully for UUID: {contact_uuid}")
                return {
                    "success": True,
                    "contact": contact_data,
                    "message": "Contact retrieved successfully"
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response for contact UUID: {contact_uuid}. Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response for contact UUID: {contact_uuid}",
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }
        else:
            logger.warning(f"Failed to retrieve contact for UUID {contact_uuid}. Status: {response.status_code}, Error: {response.text}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "content_type": content_type
            }
    except requests.exceptions.Timeout:
        logger.warning(f"Request timed out for get_contact_by_uuid for UUID: {contact_uuid}")
        return {"success": False, "error": "Request timed out after 30 seconds"}
    except Exception as e:
        logger.error(f"Error in get_contact_by_uuid for UUID {contact_uuid}: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def create_contact_address(address_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new address for a contact and link it to the contact, or update an existing address.
    
    Args:
        address_data: Dictionary containing address information with fields like:
            - contact.uuid: UUID of the contact to link the address to (required)
            - uuid: UUID of existing address to update (optional - if provided, will update instead of create)
            - address_label: A user defined label of address (e.g., "Head Office", "Billing Address", "Home", "Work")
            - address_1: The first line of the street address (e.g., street name and number, P.O Box)
            - address_2: The second line of the street address (e.g. apartment, suite, unit, building)
            - address_3: Address line for complex address
            - city: City name
            - county: the county, region or administrative area
            - country: The country. region or administrative area
            - district: A district or specific area within a city
            - suburb: The suburb or specific locality name within a city or town
            - state: The state, province or territory
            - country_code: The two letter ISO of country
            - post_code: The postal code or ZIP code for the address
            - latitude: The geographic latitude coordinate of the address
            - longitude: The geographic longitude coordinate of the address
            - geojson: GEOJSON representation of the address point
    
    Returns:
        Dictionary with success status and created/updated address details or error information
    """
    logger.info(f"Calling create_contact_address tool with data: {address_data}")
    
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        logger.error("Instance URL and API key not configured for create_contact_address")
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables or provide --instance-url and --instance-api-key arguments."
        }

    # Validate required fields
    if not address_data.get("contact.uuid"):
        logger.warning("contact.uuid is missing in create_contact_address data")
        return {
            "success": False,
            "error": "contact.uuid is required to link the address to a contact"
        }

    # Check if this is an update (address UUID provided) or create (no address UUID)
    is_update = "uuid" in address_data and address_data["uuid"]
    contact_uuid = address_data["contact.uuid"]
    
    # Verify the contact exists
    contact_check = get_contact_by_uuid(contact_uuid)
    if not contact_check["success"]:
        logger.warning(f"Contact with UUID {contact_uuid} does not exist in create_contact_address. Error: {contact_check.get('error')}")
        return {
            "success": False,
            "error": f"Contact with UUID {contact_uuid} does not exist",
            "contact_check_error": contact_check.get("error")
        }
    #call the get api for address contact
    # Log existing addresses for the contact
    try:
        existing_addresses = get_contact_addresses_by_uuid(contact_uuid)
        if existing_addresses["success"]:
            address_count = len(existing_addresses["addresses"].get("data", []))
            logger.info(f"Contact {contact_uuid} currently has {address_count} addresses")
        else:
            logger.warning(f"Could not retrieve existing addresses for contact {contact_uuid}: {existing_addresses['error']}")
    except Exception as e:
        logger.warning(f"Error checking existing addresses for contact {contact_uuid}: {str(e)}")

    # Determine the URL and method based on whether it's create or update
    if is_update:
        # Update existing address
        address_uuid = address_data["uuid"]
        url = f"{INSTANCE_URL}/crm/api/v2/contacts/addresses/{address_uuid}"
        method = "PUT"
        logger.info(f"Updating existing address with UUID: {address_uuid}")
    else:
        # Create new address
        url = f"{INSTANCE_URL}/crm/api/v2/contacts/addresses"
        method = "POST"
        logger.info(f"Creating new address for contact UUID: {contact_uuid}")

    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        if method == "POST":
            response = requests.post(url, headers=headers, json=address_data, timeout=30)
        else:
            response = requests.put(url, headers=headers, json=address_data, timeout=30)
        
        logger.info(f"create_contact_address tool finished. Response status: {response.status_code}")
        
        # Check if response is HTML instead of JSON
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type or response.text.strip().startswith('<'):
            action = "update" if is_update else "create"
            logger.warning(f"Received HTML response instead of JSON when trying to {action} address for contact UUID: {contact_uuid}")
            return {
                "success": False,
                "error": f"Received HTML response instead of JSON when trying to {action} address for contact UUID: {contact_uuid}",
                "status_code": response.status_code,
                "content_type": content_type,
                "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
            }
        
        if response.status_code in [200, 201]:
            try:
                address_result = response.json()
                action = "updated" if is_update else "created"
                logger.info(f"Address {action} successfully and linked to contact for UUID: {contact_uuid}")
                return {
                    "success": True,
                    "address": address_result,
                    "contact_uuid": contact_uuid,
                    "action": action,
                    "message": f"Address {action} successfully and linked to contact"
                }
            except json.JSONDecodeError as e:
                action = "update" if is_update else "create"
                logger.error(f"Failed to parse JSON response when trying to {action} address for contact UUID: {contact_uuid}. Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response when trying to {action} address for contact UUID: {contact_uuid}",
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }
        else:
            action = "update" if is_update else "create"
            logger.warning(f"Failed to {action} address for contact UUID {contact_uuid}. Status: {response.status_code}, Error: {response.text}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "content_type": content_type
            }
    except requests.exceptions.Timeout:
        action = "update" if is_update else "create"
        logger.warning(f"Request timed out for {action} address for contact UUID: {contact_uuid}")
        return {"success": False, "error": "Request timed out after 30 seconds"}
    except Exception as e:
        action = "update" if is_update else "create"
        logger.error(f"Error in {action} address for contact UUID {contact_uuid}: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def save_contact(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save a new contact or update an existing contact in the CRM system.
    
    Args:
        contact_data: Dictionary containing contact information with fields like:
            - prefix: Contact's prefix
            - first_name: Contact's first name
            - last_name: Contact's last name
            - gender: Contact's gender
            - birth_date: Contact's birth date
            - nationality: Contact's nationality
            - job_title: Contact's job title
            - email: Contact's email address
            - email_2: Contact's second email address
            - work_phone_country_code: Contact's work phone country code
            - work_phone_number: Contact's work phone number
            - home_phone_country_code: Contact's home phone country code
            - home_phone_number: Contact's home phone number
            - mobile_phone_country_code: Contact's mobile phone country code
            - mobile_phone_number: Contact's mobile phone number
            - default_address: Associated address (uuid)
            - assigned_to: Associated user (uuid)
            - company: Associated company name (uuid)
            - type: Associated system field type (uuid)
            - category: Associated system field category (uuid)
            - lead_source: Associated system field lead source (uuid)
            - facebook_link: Contact's facebook link
            - twitter_link: Contact's twitter link
            - youtube_link: Contact's youtube link
            - linkedin_link: Contact's linkedin link
            - instagram_link: Contact's instagram link
            - snapchat_link: Contact's snapchat link
            - social_1_link: Contact's social 1 link
            - social_2_link: Contact's social 2 link
            - has_alert_message_on_view: alert message to show when viewing the contact details
            - alert_message_on_view: message shown when viewing the contact details
            - has_alert_message_on_edit: alert message to show when editing the contact details
            - alert_message_on_edit: message shown when editing the contact details
            - notes: Additional notes about the contact
            - stripe_id: Contact's stripe id
            - owner_company: Contact person who owns the contact
            - custom_field: Custom fields for the contact

    Returns:
        Dictionary with success status and result or error information
    """
    logger.info(f"Starting save_contact operation with data: {contact_data}")
    
    if not INSTANCE_URL or not INSTANCE_API_KEY:
        logger.error("Instance URL and API key not configured for save_contact")
        return {
            "success": False,
            "error": "Instance URL and API key not configured. Please set CRM_INSTANCE_URL and CRM_INSTANCE_API_KEY environment variables or provide --instance-url and --instance-api-key arguments."
        }

    # # Validate relationship fields before saving
    # validation_result = validate_contact_relationships(contact_data)
    # if not validation_result["success"]:
    #     logger.warning(f"Relationship validation failed for save_contact. Errors: {validation_result['validation_errors']}")
    #     return validation_result
    
    # # Handle default_address creation if provided but doesn't exist
    # temp_address_data = None  # Initialize variable for scope
    
    # if "default_address" in contact_data and contact_data["default_address"]:
    #     # Check if this is an address object (not a UUID) that needs to be created
    #     if isinstance(contact_data["default_address"], dict):
    #         address_data = contact_data["default_address"].copy()
            
    #         # Store the address data temporarily - we'll create it after the contact is saved
    #         temp_address_data = address_data.copy()
    #         # Remove the address object from contact_data for now
    #         del contact_data["default_address"]
    #         logger.info("Address data stored for creation after contact is saved")
    #     else:
    #         # It's already a UUID, proceed normally
    #         logger.info(f"Using existing address UUID: {contact_data['default_address']}")
    #         pass
    
    # # Log validated UUIDs for debugging/auditing
    # if "validated_uuids" in validation_result and validation_result["validated_uuids"]:
    #     print(f"Validated relationship fields: {validation_result['validated_uuids']}")
    
    # # Update contact_data with validated UUIDs (optional - for consistency)
    # validated_uuids = validation_result.get("validated_uuids", {})
    # for field_name, uuid_value in validated_uuids.items():
    #     contact_data[field_name] = uuid_value

    url = f"{INSTANCE_URL}/crm/api/v2/contacts"
    headers = {
        "Authorization": INSTANCE_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        # Determine if this is a new contact or update based on presence of UUID
        if "uuid" in contact_data:
            # Update existing contact
            contact_uuid = contact_data["uuid"]
            url = f"{INSTANCE_URL}/crm/api/v2/contacts/{contact_uuid}"
            response = requests.put(url, headers=headers, json=contact_data, timeout=30)
            logger.info(f"Attempting to update contact with UUID: {contact_uuid}")
            
            # Log existing addresses for the contact being updated
            try:
                existing_addresses = get_contact_addresses_by_uuid(contact_uuid)
                if existing_addresses["success"]:
                    address_count = len(existing_addresses["addresses"].get("data", []))
                    logger.info(f"Contact {contact_uuid} currently has {address_count} addresses")
                else:
                    logger.warning(f"Could not retrieve existing addresses for contact {contact_uuid}: {existing_addresses['error']}")
            except Exception as e:
                logger.warning(f"Error checking existing addresses for contact {contact_uuid}: {str(e)}")
        else:
            # Create new contact
            response = requests.post(url, headers=headers, json=contact_data, timeout=30)
            logger.info("Attempting to create new contact")
        
        logger.info(f"save_contact tool finished. Response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            try:
                contact_result = response.json()
                logger.info(f"Contact {'created' if response.status_code == 201 else 'updated'} successfully with UUID: {contact_result.get('uuid', 'N/A')}")
                
                return {
                    "success": True,
                    "result": contact_result,
                    "message": "Contact saved successfully" if response.status_code == 201 else "Contact updated successfully"
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response when trying to save contact. Error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response when trying to save contact",
                    "status_code": response.status_code,
                    "response_preview": response.text[:200] + "..." if len(response.text) > 200 else response.text
                }
            
        #     # Handle default_address creation for new contacts
        #     if response.status_code == 201 and temp_address_data:
        #         # This was a new contact, now create the address using the generated contact UUID
        #         contact_uuid = contact_result.get("uuid")
        #         if not contact_uuid:
        #             logger.warning("Contact created but no UUID returned in response for address creation")
        #             return {
        #                 "success": False,
        #                 "error": "Contact created but no UUID returned to create address"
        #             }
                
        #         # Set the contact UUID for the address
        #         temp_address_data["contact_uuid"] = contact_uuid
        #         logger.info(f"Creating address for contact UUID: {contact_uuid}")
                
        #         address_result = create_contact_address(temp_address_data)
                
        #         if address_result["success"]:
        #             # Update the contact with the new address UUID
        #             update_url = f"{INSTANCE_URL}/crm/api/v2/contacts/{contact_uuid}"
        #             update_data = {"default_address": address_result["address"]["uuid"]}
                    
        #             try:
        #                 update_response = requests.patch(update_url, headers=headers, json=update_data, timeout=30)
        #                 if update_response.status_code == 200:
        #                     logger.info(f"Created default address for new contact: {address_result['address']['uuid']}")
        #                     # Update the result to include the address information
        #                     contact_result["default_address"] = address_result["address"]["uuid"]
        #                 else:
        #                     logger.warning(f"Contact created but failed to update with address UUID: {update_response.text}")
        #             except Exception as e:
        #                 logger.warning(f"Contact created but failed to update with address UUID: {str(e)}")
        #         else:
        #             logger.warning(f"Contact created but failed to create default address: {address_result['error']}")
            
        #     return {
        #         "success": True,
        #         "result": contact_result,
        #         "message": "Contact saved successfully" if response.status_code == 201 else "Contact updated successfully"
        #     }
        else:
            logger.warning(f"Failed to save contact. Status: {response.status_code}, Error: {response.text}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }
    except requests.exceptions.Timeout:
        logger.warning("Request timed out for save_contact")
        return {"success": False, "error": "Request timed out after 30 seconds"}
    except Exception as e:
        logger.error(f"Error in save_contact: {str(e)}")
        return {"success": False, "error": str(e)}


def validate_contact_relationships(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that all relationship fields reference valid UUIDs from their respective tables.
    
    Args:
        contact_data: Dictionary containing contact information
        
    Returns:
        Dictionary with validation success status, any error messages, and validated UUID values
    """
    relationship_fields = {
        "default_address": "/crm/api/v2/contacts/addresses",
        "assigned_to": "/crm/api/v2/contacts",
        "company": "/crm/api/v2/companies",
        "type": "/crm/api/v2/system-fields",
        "category": "/crm/api/v2/system-fields",
        "lead_source": "/crm/api/v2/system-fields",
        "owner_company": "/crm/api/v2/companies"
    }
    
    validation_errors = []
    validated_uuids = {}
    
    for field_name, endpoint in relationship_fields.items():
        if field_name in contact_data and contact_data[field_name]:
            uuid_value = contact_data[field_name]
            
            # Check if the referenced entity exists
            entity_exists = check_entity_exists(endpoint, uuid_value)
            if not entity_exists:
                validation_errors.append(f"Referenced {field_name} with UUID {uuid_value} does not exist in the system")
            else:
                # Store the validated UUID value
                validated_uuids[field_name] = uuid_value
    
    if validation_errors:
        return {
            "success": False,
            "error": "Relationship validation failed",
            "validation_errors": validation_errors,
            "validated_uuids": validated_uuids
        }
    
    return {
        "success": True,
        "validated_uuids": validated_uuids,
        "message": f"Successfully validated {len(validated_uuids)} relationship fields"
    }


def check_entity_exists(endpoint: str, uuid_value: str) -> bool:
    """
    Check if an entity with the given UUID exists in the specified endpoint.
    
    Args:
        endpoint: API endpoint to check
        uuid_value: UUID to validate
        
    Returns:
        True if entity exists, False otherwise
    """
    try:
        url = f"{INSTANCE_URL}{endpoint}/{uuid_value}"
        headers = {
            "Authorization": INSTANCE_API_KEY,
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        # If we can't verify, assume it's valid to avoid blocking the save operation
        # In production, you might want to log this and handle it differently
        return True

# -------------------------
# Tool Information
# -------------------------

@mcp.tool()
def list_available_tools() -> Dict[str, Any]:
    """
    List all available tools in this MCP CRM server with their descriptions and parameters.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - success (bool): Whether the operation was successful
            - tools (list): List of available tools with their information
            - total_tools (int): Total number of available tools
    """
    logger.info("Calling list_available_tools tool...")
    
    tools_info = [
        {
            "name": "Get Contacts",
            "description": "Get all contacts from the CRM module",
            "parameters": {},
            "returns": "Contacts data or error information"
        },
        {
            "name": "Get Contact Relationships",
            "description": "Get contact relationships from the CRM module", 
            "parameters": {},
            "returns": "Contact relationships data or error information"
        },
        {
            "name": "Get Contact Addresses",
            "description": "Get contact addresses from the CRM module",
            "parameters": {},
            "returns": "Contact addresses data or error information"
        },
        {
            "name": "Get Companies",
            "description": "Get all companies from the CRM module",
            "parameters": {},
            "returns": "Companies data or error information"
        },
        {
            "name": "Get Company Relationships",
            "description": "Get company relationships from the CRM module",
            "parameters": {},
            "returns": "Company relationships data or error information"
        },
        {
            "name": "Get Company Addresses",
            "description": "Get company addresses from the CRM module",
            "parameters": {},
            "returns": "Company addresses data or error information"
        },
        {
            "name": "Get System Fields",
            "description": "Get system fields from the CRM module",
            "parameters": {},
            "returns": "System fields data or error information"
        },
        {
            "name": "Get Contact System Fields",
            "description": "Get contact custom fields from the CRM module",
            "parameters": {},
            "returns": "Contact custom fields data or error information"
        },
        {
            "name": "Get Company System Fields",
            "description": "Get company custom fields from the CRM module",
            "parameters": {},
            "returns": "Company custom fields data or error information"
        },
        # {
        #     "name": "get_contact_addresses_by_uuid",
        #     "description": "Get addresses for a specific contact by UUID",
        #     "parameters": {
        #         "contact_uuid": "string - The UUID of the contact"
        #     },
        #     "returns": "Contact addresses data or error information"
        # },
        # {
        #     "name": "get_contact_by_uuid",
        #     "description": "Get a specific contact by UUID",
        #     "parameters": {
        #         "contact_uuid": "string - The UUID of the contact"
        #     },
        #     "returns": "Contact data or error information"
        # },
        {
            "name": "Save contact",
            "description": "Save or update a contact in the CRM module",
            "parameters": {
                "contact_data": "object - Contact data to save"
            },
            "returns": "Save operation result or error information"
        },
        # {
        #     "name": "list_available_tools",
        #     "description": "List all available tools in this MCP CRM server",
        #     "parameters": {},
        #     "returns": "List of available tools with descriptions"
        # }
    ]
    
    result = {
        "success": True,
        "tools": tools_info,
        "total_tools": len(tools_info),
        "message": f"Successfully listed {len(tools_info)} available tools"
    }
    
    logger.info(f"list_available_tools tool finished. Result: {result}")
    return result

# -------------------------
# Entry Point
# -------------------------
if __name__ == "__main__":
    logger.info("Starting MCP CRM Server...")
    logger.info(f"INSTANCE_URL: {INSTANCE_URL}")
    logger.info(f"INSTANCE_API_KEY: {INSTANCE_API_KEY[:10] if INSTANCE_API_KEY else 'None'}...")
    logger.info("About to call mcp.run(transport='stdio')")
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Error in mcp.run: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
else:
    # When imported as a module, just log that the module was loaded
    logger.info("MCP CRM Server module loaded successfully")