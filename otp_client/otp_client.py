#!/usr/bin/env python3
"""
OTP Service Client Library

A Python client library for interacting with the OTP Management Service API.

Usage:
    from otp_client import OTPServiceClient
    
    client = OTPServiceClient("http://localhost:8000", "your-api-key")
    
    # Create a client
    client.create_client("GitHub")
    
    # Generate OTP
    otp = client.generate_otp("GitHub")
    print(f"OTP: {otp}")
"""

import requests
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OTPServiceException(Exception):
    """Base exception for OTP Service client"""
    pass


class AuthenticationError(OTPServiceException):
    """Authentication failed"""
    pass


class ClientNotFoundError(OTPServiceException):
    """Client not found"""
    pass


class RateLimitError(OTPServiceException):
    """Rate limit exceeded"""
    pass


class OTPServiceClient:
    """
    Client library for the OTP Management Service
    
    Args:
        base_url: Base URL of the OTP service
        api_key: API key for authentication
        auto_authenticate: Automatically authenticate on initialization
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        auto_authenticate: bool = True
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.token = None
        self.headers = {}
        
        if auto_authenticate and api_key:
            self.authenticate()
    
    def authenticate(self) -> str:
        """
        Authenticate with the service and get a JWT token
        
        Returns:
            The JWT access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/token",
                json={"api_key": self.api_key},
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            
            response.raise_for_status()
            data = response.json()
            
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            
            logger.info("Successfully authenticated with OTP service")
            return self.token
            
        except requests.RequestException as e:
            raise AuthenticationError(f"Authentication failed: {e}")
    
    def _ensure_authenticated(self):
        """Ensure we have a valid token"""
        if not self.token:
            if not self.api_key:
                raise AuthenticationError("No API key provided")
            self.authenticate()
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle API response and raise appropriate exceptions
        
        Args:
            response: The response object
            
        Returns:
            Parsed JSON response
            
        Raises:
            Various exceptions based on response status
        """
        if response.status_code == 401:
            raise AuthenticationError("Invalid or expired token")
        elif response.status_code == 404:
            raise ClientNotFoundError(response.json().get("error", "Not found"))
        elif response.status_code == 429:
            raise RateLimitError(response.json().get("error", "Rate limit exceeded"))
        
        response.raise_for_status()
        
        if response.status_code == 204:
            return {}
        
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check service health
        
        Returns:
            Health status information
        """
        response = requests.get(f"{self.base_url}/health", timeout=5)
        return self._handle_response(response)
    
    def create_client(
        self,
        name: str,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new OTP client
        
        Args:
            name: Client name
            secret: Optional TOTP secret (auto-generated if not provided)
            
        Returns:
            Client information including secret and QR code URL
        """
        self._ensure_authenticated()
        
        data = {"name": name}
        if secret:
            data["secret"] = secret
        
        response = requests.post(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            json=data,
            timeout=10
        )
        
        return self._handle_response(response)
    
    def import_from_qr(
        self,
        name: str,
        qr_file_path: str
    ) -> Dict[str, Any]:
        """
        Import a client from a QR code image
        
        Args:
            name: Client name
            qr_file_path: Path to QR code image file
            
        Returns:
            Client information
        """
        self._ensure_authenticated()
        
        qr_path = Path(qr_file_path)
        if not qr_path.exists():
            raise FileNotFoundError(f"QR code file not found: {qr_file_path}")
        
        with open(qr_path, 'rb') as f:
            files = {'qr_file': (qr_path.name, f, 'image/png')}
            response = requests.post(
                f"{self.base_url}/api/v1/clients/import-qr",
                headers=self.headers,
                params={"name": name},
                files=files,
                timeout=10
            )
        
        return self._handle_response(response)
    
    def list_clients(self) -> List[Dict[str, Any]]:
        """
        List all OTP clients
        
        Returns:
            List of client information
        """
        self._ensure_authenticated()
        
        response = requests.get(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            timeout=10
        )
        
        data = self._handle_response(response)
        return data.get("clients", [])
    
    def get_client(self, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific client
        
        Args:
            name: Client name
            
        Returns:
            Client information
        """
        self._ensure_authenticated()
        
        response = requests.get(
            f"{self.base_url}/api/v1/clients/{name}",
            headers=self.headers,
            timeout=10
        )
        
        return self._handle_response(response)
    
    def generate_otp(self, name: str) -> str:
        """
        Generate a one-time password for a client
        
        Args:
            name: Client name
            
        Returns:
            The 6-digit OTP code
        """
        self._ensure_authenticated()
        
        response = requests.post(
            f"{self.base_url}/api/v1/clients/{name}/generate",
            headers=self.headers,
            timeout=10
        )
        
        data = self._handle_response(response)
        return data["otp"]
    
    def download_qr_code(
        self,
        name: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Download QR code for a client
        
        Args:
            name: Client name
            output_path: Optional path to save the QR code (default: {name}_qr.png)
            
        Returns:
            Path to the saved QR code file
        """
        self._ensure_authenticated()
        
        response = requests.get(
            f"{self.base_url}/api/v1/clients/{name}/qr",
            headers=self.headers,
            timeout=10
        )
        
        if response.status_code != 200:
            self._handle_response(response)
        
        if not output_path:
            output_path = f"{name}_qr.png"
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"QR code saved to {output_path}")
        return output_path
    
    def delete_client(self, name: str) -> bool:
        """
        Delete a client
        
        Args:
            name: Client name
            
        Returns:
            True if successful
        """
        self._ensure_authenticated()
        
        response = requests.delete(
            f"{self.base_url}/api/v1/clients/{name}",
            headers=self.headers,
            timeout=10
        )
        
        self._handle_response(response)
        logger.info(f"Client '{name}' deleted successfully")
        return True


# Convenience functions for quick usage
def create_client(
    name: str,
    secret: Optional[str] = None,
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Quick function to create a client"""
    client = OTPServiceClient(base_url, api_key)
    return client.create_client(name, secret)


def generate_otp(
    name: str,
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None
) -> str:
    """Quick function to generate an OTP"""
    client = OTPServiceClient(base_url, api_key)
    return client.generate_otp(name)


# Example usage
if __name__ == "__main__":
    import os
    
    # Get API key from environment or use default
    API_KEY = os.getenv("OTP_API_KEY", "your-api-key")
    BASE_URL = os.getenv("OTP_BASE_URL", "http://localhost:8000")
    
    # Create client
    client = OTPServiceClient(BASE_URL, API_KEY)
    
    # Example operations
    try:
        # Check health
        health = client.health_check()
        print(f"Service health: {health['status']}")
        
        # Create a client
        print("\nCreating client 'ExampleService'...")
        new_client = client.create_client("ExampleService")
        print(f"Client created with secret: {new_client['secret']}")
        
        # List all clients
        print("\nListing all clients...")
        clients = client.list_clients()
        for c in clients:
            print(f"  - {c['name']}")
        
        # Generate OTP
        print("\nGenerating OTP for 'ExampleService'...")
        otp = client.generate_otp("ExampleService")
        print(f"OTP: {otp}")
        
        # Download QR code
        print("\nDownloading QR code...")
        qr_path = client.download_qr_code("ExampleService")
        print(f"QR code saved to: {qr_path}")
        
        # Clean up
        print("\nDeleting client...")
        client.delete_client("ExampleService")
        print("Client deleted")
        
    except OTPServiceException as e:
        print(f"Error: {e}")
