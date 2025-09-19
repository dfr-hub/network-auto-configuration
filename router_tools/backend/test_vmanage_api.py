#!/usr/bin/env python3
"""
Test script untuk menguji vManage API responses
"""

import requests
import json
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def test_vmanage_endpoints():
    """Test berbagai endpoint vManage"""
    
    # vManage connection details
    host = "36.67.62.248"
    username = input("Enter vManage username: ")
    password = input("Enter vManage password: ")
    
    base_url = f"https://{host}:443/dataservice"
    
    # Create session
    session = requests.Session()
    session.verify = False
    
    print(f"\n🔍 Testing vManage API at {host}")
    print("=" * 50)
    
    # Test 1: Check if server is reachable
    print("\n1. Testing server reachability...")
    try:
        response = session.get(f"https://{host}:443", timeout=10)
        print(f"   ✅ Server reachable - Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Server not reachable: {e}")
        return
    
    # Test 2: Try different authentication endpoints
    auth_endpoints = [
        "/j_security_check",
        "/client/server", 
        "/login",
        "/authenticate"
    ]
    
    print("\n2. Testing authentication endpoints...")
    for endpoint in auth_endpoints:
        try:
            url = f"{base_url}{endpoint}"
            print(f"   Testing: {url}")
            
            if endpoint == "/j_security_check":
                # Traditional form-based auth
                auth_data = {
                    'j_username': username,
                    'j_password': password
                }
                response = session.post(url, data=auth_data, timeout=10)
            elif endpoint == "/client/server":
                # Just GET to check if endpoint exists
                response = session.get(url, timeout=10)
            else:
                # JSON-based auth
                auth_data = {
                    'username': username,
                    'password': password
                }
                response = session.post(url, json=auth_data, timeout=10)
            
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            
            if response.status_code < 400:
                try:
                    json_response = response.json()
                    print(f"   Response: {json.dumps(json_response, indent=2)[:500]}...")
                except:
                    print(f"   Response (text): {response.text[:200]}...")
            else:
                print(f"   Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Error testing {endpoint}: {e}")
        
        print()
    
    # Test 3: Try basic authentication
    print("\n3. Testing basic authentication...")
    try:
        session.auth = (username, password)
        response = session.get(f"{base_url}/device", timeout=10)
        print(f"   Status with basic auth: {response.status_code}")
        if response.status_code < 400:
            try:
                json_response = response.json()
                print(f"   Device data: {json.dumps(json_response, indent=2)[:300]}...")
            except:
                print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Basic auth error: {e}")
    
    # Test 4: Try to get API documentation or available endpoints
    print("\n4. Testing API discovery endpoints...")
    discovery_endpoints = [
        "/",
        "/api",
        "/swagger",
        "/docs", 
        "/help",
        "/version"
    ]
    
    for endpoint in discovery_endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = session.get(url, timeout=5)
            print(f"   {endpoint}: Status {response.status_code}")
            if response.status_code == 200:
                print(f"   Content-Type: {response.headers.get('content-type', 'Unknown')}")
                print(f"   Content length: {len(response.text)}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_vmanage_endpoints()