"""
Google Secret Manager helper module.
Provides utilities for securely accessing secrets.
"""

import os
import logging
from functools import lru_cache
from typing import Optional
from google.cloud import secretmanager
from google.api_core import exceptions

logger = logging.getLogger(__name__)


class SecretManagerClient:
    """Client for Google Cloud Secret Manager."""
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Secret Manager client.
        
        Args:
            project_id: GCP project ID (defaults to env var GCP_PROJECT_ID)
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be set")
        
        # Client automatically uses Cloud Run's service account
        self.client = secretmanager.SecretManagerServiceClient()
    
    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str, version: str = "latest") -> str:
        """
        Get a secret value from Secret Manager.
        
        Results are cached in memory to avoid repeated API calls.
        
        Args:
            secret_name: Name of the secret
            version: Version of the secret (default: "latest")
        
        Returns:
            Secret value as string
        
        Raises:
            ValueError: If secret not found or access denied
        """
        try:
            # Build the secret version path
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            
            logger.info(f"Accessing secret: {secret_name} (version: {version})")
            
            # Access the secret
            response = self.client.access_secret_version(request={"name": name})
            
            # Decode and return the secret value
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.info(f"✅ Successfully retrieved secret: {secret_name}")
            return secret_value
            
        except exceptions.NotFound:
            error_msg = f"Secret '{secret_name}' not found in project {self.project_id}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        except exceptions.PermissionDenied:
            error_msg = f"Permission denied accessing secret '{secret_name}'. Check IAM permissions."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        except Exception as e:
            error_msg = f"Error accessing secret '{secret_name}': {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
    
    def get_secret_or_env(self, secret_name: str, env_var: str, default: Optional[str] = None) -> str:
        """
        Try to get secret from Secret Manager, fall back to environment variable.
        
        This is useful for local development where you might not have Secret Manager access.
        
        Args:
            secret_name: Name of the secret in Secret Manager
            env_var: Environment variable name as fallback
            default: Default value if neither secret nor env var exists
        
        Returns:
            Secret value, environment variable value, or default
        """
        # Try Secret Manager first (production)
        try:
            return self.get_secret(secret_name)
        except Exception as e:
            logger.warning(f"Could not access secret '{secret_name}': {e}")
        
        # Fall back to environment variable (local development)
        env_value = os.getenv(env_var)
        if env_value:
            logger.info(f"Using environment variable {env_var} instead of secret")
            return env_value
        
        # Use default if provided
        if default is not None:
            logger.warning(f"Using default value for {secret_name}")
            return default
        
        raise ValueError(f"Could not find secret '{secret_name}' or env var '{env_var}'")
    
    def create_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Create a new secret (admin operation).
        
        Args:
            secret_name: Name for the new secret
            secret_value: Value to store
        """
        try:
            parent = f"projects/{self.project_id}"
            
            # Create the secret
            secret = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_name,
                    "secret": {
                        "replication": {"automatic": {}},
                    },
                }
            )
            
            logger.info(f"Created secret: {secret.name}")
            
            # Add the secret value as the first version
            self.client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"✅ Secret '{secret_name}' created successfully")
            
        except Exception as e:
            logger.error(f"❌ Error creating secret '{secret_name}': {e}")
            raise
    
    def update_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Update a secret (creates a new version).
        
        Args:
            secret_name: Name of the secret to update
            secret_value: New value
        """
        try:
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            
            # Add new version
            self.client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"✅ Secret '{secret_name}' updated successfully")
            
        except Exception as e:
            logger.error(f"❌ Error updating secret '{secret_name}': {e}")
            raise
    
    def list_secrets(self) -> list:
        """List all secrets in the project."""
        try:
            parent = f"projects/{self.project_id}"
            secrets = self.client.list_secrets(request={"parent": parent})
            return [secret.name for secret in secrets]
        except Exception as e:
            logger.error(f"❌ Error listing secrets: {e}")
            raise


# Global singleton instance
_secret_manager_client: Optional[SecretManagerClient] = None


def get_secret_manager() -> SecretManagerClient:
    """Get or create the global Secret Manager client."""
    global _secret_manager_client
    if _secret_manager_client is None:
        _secret_manager_client = SecretManagerClient()
    return _secret_manager_client


# Convenience function
def get_secret(secret_name: str, version: str = "latest") -> str:
    """
    Convenience function to get a secret.
    
    Usage:
        from utils.secret_manager import get_secret
        api_key = get_secret("insites-instance-api-key")
    """
    return get_secret_manager().get_secret(secret_name, version)