#!/usr/bin/env python3
"""
OTP Service API Test Suite

Tests all API endpoints with various scenarios
"""

import requests
import json
import time
import os
from pathlib import Path

class OTPServiceTester:
    def __init__(self, base_url="http://localhost:8000", api_key=None):
        self.base_url = base_url
        self.api_key = api_key or os.getenv("API_KEY", "test-api-key")
        self.token = None
        self.headers = {}
        
    def test_health(self):
        """Test health endpoint"""
        print("\n=== Testing Health Endpoint ===")
        response = requests.get(f"{self.base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "degraded"]
        print("✓ Health check passed")
        
    def test_get_token(self):
        """Test token generation"""
        print("\n=== Testing Token Generation ===")
        response = requests.post(
            f"{self.base_url}/api/v1/token",
            json={"api_key": self.api_key}
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print("✓ Token generation passed")
            return True
        else:
            print(f"✗ Token generation failed: {response.text}")
            return False
            
    def test_create_client(self, name="TestClient", secret=None):
        """Test creating a client"""
        print(f"\n=== Testing Create Client: {name} ===")
        data = {"name": name}
        if secret:
            data["secret"] = secret
            
        response = requests.post(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            json=data
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 201:
            print("✓ Client creation passed")
            return response.json()
        else:
            print(f"✗ Client creation failed")
            return None
            
    def test_list_clients(self):
        """Test listing all clients"""
        print("\n=== Testing List Clients ===")
        response = requests.get(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✓ List clients passed")
            return response.json()
        else:
            print(f"✗ List clients failed")
            return None
            
    def test_get_client(self, name):
        """Test getting client details"""
        print(f"\n=== Testing Get Client: {name} ===")
        response = requests.get(
            f"{self.base_url}/api/v1/clients/{name}",
            headers=self.headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✓ Get client passed")
            return response.json()
        else:
            print(f"✗ Get client failed")
            return None
            
    def test_generate_otp(self, name):
        """Test OTP generation"""
        print(f"\n=== Testing Generate OTP: {name} ===")
        response = requests.post(
            f"{self.base_url}/api/v1/clients/{name}/generate",
            headers=self.headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✓ Generate OTP passed")
            return response.json()
        else:
            print(f"✗ Generate OTP failed")
            return None
            
    def test_get_qr_code(self, name):
        """Test QR code download"""
        print(f"\n=== Testing Get QR Code: {name} ===")
        response = requests.get(
            f"{self.base_url}/api/v1/clients/{name}/qr",
            headers=self.headers
        )
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            # Save QR code
            qr_path = f"/tmp/test_{name}_qr.png"
            with open(qr_path, 'wb') as f:
                f.write(response.content)
            print(f"✓ Get QR code passed - saved to {qr_path}")
            return qr_path
        else:
            print(f"✗ Get QR code failed")
            return None
            
    def test_delete_client(self, name):
        """Test deleting a client"""
        print(f"\n=== Testing Delete Client: {name} ===")
        response = requests.delete(
            f"{self.base_url}/api/v1/clients/{name}",
            headers=self.headers
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 204:
            print("✓ Delete client passed")
            return True
        else:
            print(f"✗ Delete client failed: {response.text}")
            return False
            
    def test_rate_limiting(self):
        """Test rate limiting"""
        print("\n=== Testing Rate Limiting ===")
        print("Making rapid requests...")
        
        success_count = 0
        rate_limited = False
        
        for i in range(150):  # Exceed default rate limit
            response = requests.get(
                f"{self.base_url}/api/v1/clients",
                headers=self.headers
            )
            
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited = True
                print(f"✓ Rate limiting triggered after {success_count} requests")
                break
                
        if rate_limited:
            print("✓ Rate limiting test passed")
        else:
            print("✗ Rate limiting test failed - no limit enforced")
            
    def test_invalid_token(self):
        """Test authentication with invalid token"""
        print("\n=== Testing Invalid Token ===")
        invalid_headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(
            f"{self.base_url}/api/v1/clients",
            headers=invalid_headers
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Invalid token correctly rejected")
        else:
            print("✗ Invalid token test failed")
            
    def test_duplicate_client(self, name):
        """Test creating duplicate client"""
        print(f"\n=== Testing Duplicate Client: {name} ===")
        response = requests.post(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            json={"name": name}
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 409:
            print("✓ Duplicate client correctly rejected")
        else:
            print("✗ Duplicate client test failed")
            
    def test_invalid_client_name(self):
        """Test creating client with invalid name"""
        print("\n=== Testing Invalid Client Name ===")
        response = requests.post(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            json={"name": "Test@Client#123"}
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 422:  # Validation error
            print("✓ Invalid client name correctly rejected")
        else:
            print("✗ Invalid client name test failed")
            
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("OTP SERVICE API TEST SUITE")
        print("=" * 60)
        
        try:
            # Basic tests
            self.test_health()
            
            if not self.test_get_token():
                print("\n✗ Cannot continue - token generation failed")
                return
                
            # Client operations
            client1 = self.test_create_client("TestService1")
            client2 = self.test_create_client("TestService2", "JBSWY3DPEHPK3PXP")
            
            self.test_list_clients()
            
            if client1:
                self.test_get_client(client1["name"])
                self.test_generate_otp(client1["name"])
                self.test_get_qr_code(client1["name"])
                
            # Error cases
            self.test_invalid_token()
            if client1:
                self.test_duplicate_client(client1["name"])
            self.test_invalid_client_name()
            
            # Rate limiting (commented out by default as it's slow)
            # self.test_rate_limiting()
            
            # Cleanup
            if client1:
                self.test_delete_client(client1["name"])
            if client2:
                self.test_delete_client(client2["name"])
                
            print("\n" + "=" * 60)
            print("TEST SUITE COMPLETED")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n✗ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OTP Service API Tester")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--api-key", help="API key for authentication")
    args = parser.parse_args()
    
    tester = OTPServiceTester(args.url, args.api_key)
    tester.run_all_tests()


if __name__ == "__main__":
    main()
