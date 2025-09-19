"""
Cisco SD-WAN vManage API Client
Integration with vManage for centralized network management
"""
import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
import urllib3

# Disable SSL warnings for lab environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class VManageClient:
    """
    Cisco SD-WAN vManage API Client
    """
    
    def __init__(self, host: str, username: str, password: str, port: int = 443):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"https://{host}:{port}/dataservice"
        self.session = requests.Session()
        self.session.verify = False  # For lab environments
        self.token = None
        self.server_facts = None
        self.authenticated = False
        self.current_tenant_id = None
        self.available_tenants = []
        self.session_id = None  # raw session-id (from server facts)
        # Default headers
        self.session.headers['Accept'] = 'application/json'
        
    def authenticate(self) -> Dict:
        """
        Authenticate with vManage following Sastre implementation
        """
        try:
            # Authentication payload
            auth_data = {
                "j_username": self.username,
                "j_password": self.password
            }
            
            # Login request
            auth_url = f"{self.base_url}/j_security_check"
            response = self.session.post(auth_url, data=auth_data, verify=False)
            response.raise_for_status()
            
            # Check if login was successful (vManage returns HTML on failure)
            if b'<html>' in response.content:
                return {
                    "success": False,
                    "error": "Invalid credentials - HTML response received"
                }
            
            # Get server facts and CSRF token
            server_response = self.session.get(f"{self.base_url}/client/server", verify=False)
            server_response.raise_for_status()
            server_facts = server_response.json().get('data')
            
            if server_facts is None:
                return {
                    "success": False,
                    "error": "Could not retrieve vManage server information"
                }
            
            self.server_facts = server_facts
            
            # Set CSRF token header (introduced in 19.2)
            token = server_facts.get('CSRFToken')
            if token is not None:
                self.session.headers['X-XSRF-TOKEN'] = token
                self.token = token

            # Extract session id (naming may vary: sessionId / sessionID)
            session_id = server_facts.get('sessionId') or server_facts.get('sessionID') or server_facts.get('sessionid')
            if session_id:
                # Sastre sets 'session-id' header for all calls; replicate
                self.session.headers['session-id'] = session_id
                self.session_id = session_id
            else:
                # Fallback: some versions embed JSESSIONID cookie only
                js_cookie = self.session.cookies.get('JSESSIONID') or self.session.cookies.get('JSESSIONIDSSO')
                if js_cookie:
                    self.session_id = js_cookie  # store for debug

            # Optional debug prints (can be silenced later)
            try:
                print(f"[vManage] Auth OK - platformVersion={server_facts.get('platformVersion')} session-id={self.session_id}")
            except Exception:
                pass
            
            # Set content type header
            self.session.headers['Content-Type'] = 'application/json'
            
            self.authenticated = True
            return {
                "success": True,
                "message": "Authentication successful",
                "server_version": server_facts.get('platformVersion'),
                "is_multi_tenant": server_facts.get('tenancyMode', '') == 'MultiTenant',
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Authentication error: {str(e)}"
            }
    
    def get_devices(self) -> Dict:
        """
        Get all devices from vManage - based on successful test results
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        # Re-assert session-id header if lost
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            # Use the endpoint that worked in our test
            url = f"{self.base_url}/device"
            response = self.session.get(url, verify=False)
            
            if response.status_code == 200:
                devices_data = response.json()
                devices = devices_data.get("data", [])
                print(f"Found {len(devices)} devices from device endpoint")
                
                return {
                    "success": True,
                    "devices": devices,
                    "count": len(devices),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get devices: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting devices: {str(e)}"
            }
    
    def get_edge_devices(self) -> Dict:
        """
        Get edge devices specifically from vManage
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
            
        # Ensure tenant context headers are properly set
        if self.current_tenant_id:
            if 'VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers:
                # Re-apply tenant context
                self.session.headers['X-Tenant-Id'] = self.current_tenant_id
                print(f"[vManage] Re-applied tenant context: {self.current_tenant_id}")
            print(f"[vManage] Current tenant context: {self.current_tenant_id}")
            print(f"[vManage] Active headers: VSessionId={self.session.headers.get('VSessionId', 'None')}, X-Tenant-Id={self.session.headers.get('X-Tenant-Id', 'None')}")
        
        try:
            # We'll try several endpoints commonly used for edge inventory.
            # First successful one with non-empty edge devices will be returned.
            candidate_calls = [
                {
                    "name": "device endpoint",
                    "url": f"{self.base_url}/device",
                    "params": None,
                    "extract": lambda r: r.get('data', [])
                },
                {
                    "name": "vedge inventory",
                    "url": f"{self.base_url}/device/vedges",
                    "params": None,
                    "extract": lambda r: r.get('data', [])
                },
                {
                    "name": "cedge inventory",
                    "url": f"{self.base_url}/device/cedge",
                    "params": None,
                    "extract": lambda r: r.get('data', [])
                },
                {
                    "name": "DeviceConnectionState",
                    "url": f"{self.base_url}/data/device/state/DeviceConnectionState",
                    "params": {"startId": "0", "count": "1000"},
                    "extract": lambda r: r.get('data', [])
                },
                {
                    "name": "system device vedges",
                    "url": f"{self.base_url}/system/device/vedges",
                    "params": None,
                    "extract": lambda r: r.get('data', [])
                },
                {
                    "name": "device monitor",
                    "url": f"{self.base_url}/device/monitor",
                    "params": None,
                    "extract": lambda r: r.get('data', [])
                }
            ]

            collected_errors = []
            for call in candidate_calls:
                try:
                    print(f"[vManage] Trying endpoint: {call['name']} - {call['url']}")
                    resp = self.session.get(call['url'], params=call['params'], verify=False)
                    print(f"[vManage] {call['name']} response: HTTP {resp.status_code}")
                    
                    if resp.status_code != 200:
                        collected_errors.append(f"{call['name']} -> HTTP {resp.status_code}")
                        continue
                        
                    raw_json = resp.json()
                    devices = call['extract'](raw_json)
                    if not isinstance(devices, list):
                        # Some endpoints might return list directly
                        if isinstance(raw_json, list):
                            devices = raw_json
                        else:
                            collected_errors.append(f"{call['name']} -> unexpected structure keys={list(raw_json.keys())[:6]}")
                            continue

                    # Filter: consider additional possible fields for type: 'personality'
                    edge_devices = []
                    device_types_found = {}
                    
                    for device in devices:
                        dt = (device.get('device-type') or device.get('deviceType') or device.get('personality') or '').lower()
                        
                        # Count device types for debugging
                        device_types_found[dt] = device_types_found.get(dt, 0) + 1
                        
                        # More specific filtering to avoid false positives
                        if any(x in dt for x in ['vedge', 'cedge']) or dt in ['edge', 'sd-wan-edge']:
                            edge_devices.append(device)

                    print(f"[vManage] Endpoint {call['name']} returned {len(devices)} devices, edge subset={len(edge_devices)}")
                    if device_types_found:
                        print(f"[vManage] Device types found: {dict(device_types_found)}")
                    
                    if edge_devices:
                        return {
                            "success": True,
                            "devices": edge_devices,
                            "count": len(edge_devices),
                            "source_endpoint": call['name'],
                            "current_tenant_id": self.current_tenant_id,
                            "timestamp": datetime.now().isoformat()
                        }
                except Exception as inner_e:
                    collected_errors.append(f"{call['name']} -> exception {inner_e}")
                    continue

            # If we reach here, no endpoint produced edge devices
            return {
                "success": True,  # still success but empty, to show UI it's a valid call
                "devices": [],
                "count": 0,
                "attempted_endpoints": [c['name'] for c in candidate_calls],
                "errors": collected_errors,
                "note": "No edge devices found across tried endpoints",
                "current_tenant_id": self.current_tenant_id,
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting edge devices: {str(e)}"
            }
    
    def get_device_details(self, device_id: str) -> Dict:
        """
        Get detailed information for specific device
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/device/details"
            params = {"deviceId": device_id}
            response = self.session.get(url, params=params, verify=False)
            
            if response.status_code == 200:
                device_details = response.json()
                return {
                    "success": True,
                    "device": device_details,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get device details: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting device details: {str(e)}"
            }
    
    def get_device_config(self, device_id: str) -> Dict:
        """
        Get running configuration for device
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/template/config/running/{device_id}"
            response = self.session.get(url, verify=False)
            
            if response.status_code == 200:
                config = response.json()
                return {
                    "success": True,
                    "config": config,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get device config: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting device config: {str(e)}"
            }
    
    def get_device_status(self, device_id: str) -> Dict:
        """
        Get device status and health information
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/device/{device_id}/status"
            response = self.session.get(url, verify=False)
            
            if response.status_code == 200:
                status = response.json()
                return {
                    "success": True,
                    "status": status,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get device status: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting device status: {str(e)}"
            }
    
    def execute_device_command(self, device_id: str, command: str) -> Dict:
        """
        Execute command on device via vManage
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/device/tools/nping/{device_id}"
            
            # This would need to be adapted based on actual vManage command execution API
            # The exact endpoint varies by command type
            
            data = {
                "command": command,
                "deviceId": device_id
            }
            
            response = self.session.post(url, json=data, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to execute command: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing command: {str(e)}"
            }
    
    def get_templates(self) -> Dict:
        """
        Get all device templates from vManage
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/template/device"
            response = self.session.get(url, verify=False)
            
            if response.status_code == 200:
                templates = response.json()
                return {
                    "success": True,
                    "templates": templates.get("data", []),
                    "count": len(templates.get("data", [])),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get templates: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting templates: {str(e)}"
            }
    
    def get_policies(self) -> Dict:
        """
        Get all policies from vManage
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            url = f"{self.base_url}/template/policy/vedge"
            response = self.session.get(url, verify=False)
            
            if response.status_code == 200:
                policies = response.json()
                return {
                    "success": True,
                    "policies": policies.get("data", []),
                    "count": len(policies.get("data", [])),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get policies: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting policies: {str(e)}"
            }
    
    def get_tenants(self) -> Dict:
        """
        Get all available tenants (multitenant only)
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            # Try both endpoints for tenant list
            urls = [
                f"{self.base_url}/tenant",  # Main tenant endpoint
                f"{self.base_url}/clusterManagement/tenantList"  # Alternative endpoint
            ]
            
            for url in urls:
                response = self.session.get(url, verify=False)
                
                if response.status_code == 200:
                    tenants_data = response.json()
                    
                    # Handle different response formats
                    if isinstance(tenants_data, list):
                        tenants = tenants_data
                    elif isinstance(tenants_data, dict) and "data" in tenants_data:
                        tenants = tenants_data["data"]
                    else:
                        tenants = []
                    
                    self.available_tenants = tenants
                    
                    return {
                        "success": True,
                        "tenants": tenants,
                        "count": len(tenants),
                        "timestamp": datetime.now().isoformat(),
                        "endpoint_used": url
                    }
            
            # If both endpoints fail
            return {
                "success": False,
                "error": "Failed to get tenants from both endpoints",
                "note": "This might not be a multitenant vManage system"
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting tenants: {str(e)}"
            }
    
    def switch_tenant(self, tenant_id: str) -> Dict:
        """
        Switch to a specific tenant context using VSessionId or fallback methods
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        
        try:
            # Check if multi-tenant system
            if self.server_facts and self.server_facts.get('tenancyMode', '') == 'MultiTenant':
                user_mode = self.server_facts.get('userMode', '')
                
                # Method 1: Try VSessionId approach (requires provider permissions)
                if user_mode == 'provider':
                    url = f"{self.base_url}/tenant/{tenant_id}/vsessionid"
                    print(f"DEBUG: Switch tenant URL: {url}")
                    print(f"DEBUG: Request headers: {dict(self.session.headers)}")
                    
                    response = self.session.post(url, json={}, verify=False)
                    print(f"DEBUG: Response status: {response.status_code}")
                    print(f"DEBUG: Response text: {response.text}")
                    
                    if response.status_code == 200:
                        session_data = response.json()
                        session_id = session_data.get('VSessionId')
                        
                        if session_id:
                            # Set VSessionId header for tenant scope
                            self.session.headers['VSessionId'] = session_id
                            self.current_tenant_id = tenant_id
                            
                            return {
                                "success": True,
                                "message": f"Successfully switched to tenant {tenant_id}",
                                "tenant_id": tenant_id,
                                "session_id": session_id,
                                "method": "VSessionId",
                                "timestamp": datetime.now().isoformat()
                            }
                    
                    # If VSessionId failed due to permissions, try fallback
                    print(f"DEBUG: VSessionId failed, trying fallback method")
                
                # Method 2: Fallback - Direct tenant header approach
                # Some vManage versions accept tenant-id directly in headers
                # Remove old VSessionId if present
                if 'VSessionId' in self.session.headers:
                    del self.session.headers['VSessionId']
                
                # Set tenant context via alternative headers
                self.session.headers['X-Tenant-Id'] = tenant_id
                self.current_tenant_id = tenant_id
                
                # Test if tenant switch worked by trying to get tenant info
                test_url = f"{self.base_url}/tenant/current"
                test_response = self.session.get(test_url, verify=False)
                
                return {
                    "success": True,
                    "message": f"Switched to tenant {tenant_id} (fallback method)",
                    "tenant_id": tenant_id,
                    "method": "fallback_header",
                    "note": "Using X-Tenant-Id header method - device data will be tenant-specific",
                    "test_status": test_response.status_code if test_response else "unknown",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Not a multi-tenant vManage system"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error switching tenant: {str(e)}"
            }
    
    def get_current_tenant_info(self) -> Dict:
        """
        Get information about current tenant context
        """
        return {
            "success": True,
            "current_tenant_id": self.current_tenant_id,
            "available_tenants": self.available_tenants,
            "tenant_count": len(self.available_tenants)
        }
    
    def refresh_tenant_context(self) -> Dict:
        """
        Refresh tenant context to ensure headers are properly set
        """
        if not self.current_tenant_id:
            return {"success": True, "message": "No active tenant"}
            
        # Clear any stale tenant headers
        headers_to_clear = ['VSessionId', 'X-Tenant-Id']
        for header in headers_to_clear:
            if header in self.session.headers:
                del self.session.headers[header]
        
        # Re-establish tenant context
        return self.switch_tenant(self.current_tenant_id)
    
    def ping_device(self, device_ip: str, target_ip: str, vpn: str = "0", count: int = 5) -> Dict:
        """
        Ping from device to target IP
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        
        try:
            url = f"{self.base_url}/device/tools/ping/{device_ip}"
            payload = {
                "host": target_ip,
                "vpn": vpn,
                "count": str(count)
            }
            
            response = self.session.post(url, json=payload, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to ping: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error pinging device: {str(e)}"
            }
    
    def traceroute_device(self, device_ip: str, target_ip: str, vpn: str = "0") -> Dict:
        """
        Traceroute from device to target IP
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        
        try:
            url = f"{self.base_url}/device/tools/traceroute/{device_ip}"
            payload = {
                "host": target_ip,
                "vpn": vpn
            }
            
            response = self.session.post(url, json=payload, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to traceroute: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error traceroute from device: {str(e)}"
            }
    
    def nslookup_device(self, device_ip: str, hostname: str, vpn: str = "0", dns_server: str = "8.8.8.8") -> Dict:
        """
        NSLookup from device
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        
        try:
            url = f"{self.base_url}/device/tools/nslookup"
            params = {
                "deviceId": device_ip,
                "host": hostname,
                "vpn": vpn,
                "dns": dns_server
            }
            
            response = self.session.get(url, params=params, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to nslookup: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error nslookup from device: {str(e)}"
            }

    def get_device_arp(self, device_ip: str, vpn: str = "0") -> Dict:
        """
        Get ARP table from device
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        
        try:
            url = f"{self.base_url}/device/arp"
            params = {
                "deviceId": device_ip,
                "vpn": vpn
            }
            
            response = self.session.get(url, params=params, verify=False)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "arp_entries": result.get("data", []),
                    "count": len(result.get("data", [])),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get ARP: HTTP {response.status_code}",
                    "response": response.text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting ARP from device: {str(e)}"
            }

    def get_device_interface_status(self, device_ip: str) -> Dict:
        """
        Get interface status from device
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        
        try:
                params = {"deviceId": device_ip}
                # Try /device/interface first
                resp = self.session.get(f"{self.base_url}/device/interface", params=params, verify=False)
                if resp.status_code != 200:
                    # Fallback to /device/interface/synced per Cisco examples
                    resp = self.session.get(f"{self.base_url}/device/interface/synced", params=params, verify=False)
                if resp.status_code == 200:
                    result = resp.json()
                    data = result.get("data", result if isinstance(result, list) else [])
                    return {"success": True, "interfaces": data, "count": len(data) if isinstance(data, list) else 0, "timestamp": datetime.now().isoformat()}
                return {"success": False, "error": f"Failed to get interfaces: HTTP {resp.status_code}", "response": resp.text}
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting interfaces from device: {str(e)}"
            }

    def get_interface_statistics(self, device_ip: str, interface: Optional[str] = None, time_range: str = "last 1 hour", interval: str = "5min") -> Dict:
        """
        Get interface statistics for a device with robust endpoint and method fallbacks.
        Attempts GET and POST on /statistics/interface with optional filters.
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result

        # Ensure tenant/session headers
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id:
            if 'VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers:
                self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            base = f"{self.base_url}/statistics/interface"

            # Helper: convert common time_range strings to epoch ms range
            def parse_time_range(tr: str):
                now = datetime.utcnow()
                end_ms = int(now.timestamp()*1000)
                t = tr.strip().lower()
                if "last" in t and "hour" in t:
                    num = 1
                    for n in [1,3,6,12,24,48,72]:
                        if str(n) in t:
                            num = n
                            break
                    start = now.replace()
                    from datetime import timedelta
                    start = now - timedelta(hours=num)
                    return int(start.timestamp()*1000), end_ms
                if "last" in t and ("day" in t or "days" in t):
                    num = 1
                    for n in [1,3,7,14,30]:
                        if str(n) in t:
                            num = n
                            break
                    from datetime import timedelta
                    start = now - timedelta(days=num)
                    return int(start.timestamp()*1000), end_ms
                # default: 24 hours
                from datetime import timedelta
                start = now - timedelta(hours=24)
                return int(start.timestamp()*1000), end_ms

            start_ms, end_ms = parse_time_range(time_range)
            print(f"[vManage] Time range parsed: {time_range} -> {start_ms} to {end_ms}")

            # Normalize interval synonyms to API-accepted values
            interval_map = {
                '1h': '1hour', '1hr': '1hour', '60m': '1hour', '60min': '1hour',
                '1d': '1day', '24h': '1day'
            }
            api_interval = interval_map.get(interval.strip().lower(), interval)

            def extract_data(rjson):
                if isinstance(rjson, dict):
                    if 'data' in rjson and isinstance(rjson['data'], list):
                        return rjson['data']
                if isinstance(rjson, list):
                    return rjson
                return []

            errors = []

            # 1) Try GET with deviceId UUID resolution first (best for intervals)
            try:
                print(f"[vManage] Attempting device UUID resolution for interval support...")
                dev_resp = self.session.get(f"{self.base_url}/device", verify=False)
                if dev_resp.status_code == 200:
                    arr = extract_data(dev_resp.json())
                    uuid = None
                    for d in arr:
                        sip = d.get('system-ip') or d.get('systemIp') or d.get('system_ip') or d.get('deviceIp')
                        if sip == device_ip:
                            uuid = d.get('uuid') or d.get('deviceId') or d.get('device-id')
                            break
                    if uuid:
                        print(f"[vManage] Found device UUID: {uuid}")
                        # Try GET with deviceId uuid and time
                        p = {"deviceId": uuid, "startTime": start_ms, "endTime": end_ms, "interval": api_interval}
                        if interface:
                            p["interface"] = interface
                        print(f"[vManage] GET with deviceId params: {p}")
                        resp = self.session.get(base, params=p, verify=False)
                        print(f"[vManage] GET with deviceId response status: {resp.status_code}")
                        if resp.status_code == 200:
                            data = extract_data(resp.json())
                            if data:
                                print(f"[vManage] GET with deviceId success, data length: {len(data)}")
                                return {
                                    "success": True,
                                    "data": data,
                                    "count": len(data),
                                    "source_endpoint": f"statistics/interface GET with deviceId (interval={api_interval})",
                                    "current_tenant_id": self.current_tenant_id,
                                    "timestamp": datetime.now().isoformat()
                                }
                        else:
                            print(f"[vManage] GET with deviceId failed with status: {resp.status_code}")
                            if resp.status_code != 200:
                                print(f"[vManage] GET with deviceId failed body: {resp.text[:200]}...")
                    else:
                        print(f"[vManage] Could not find UUID for device {device_ip}")
            except Exception as e:
                print(f"[vManage] Device UUID resolution failed: {e}")

            # 2) Try GET with multiple param variants (skip for now - vManage seems to require POST)
            # Most vManage versions require POST for statistics queries
            get_param_sets = []
            for p in get_param_sets:
                try:
                    print(f"[vManage] GET interface stats with params keys={list(p.keys())}")
                    resp = self.session.get(base, params=p, verify=False)
                    print(f"[vManage] GET response status: {resp.status_code}")
                    if resp.status_code == 200:
                        json_resp = resp.json()
                        print(f"[vManage] GET response keys: {list(json_resp.keys()) if isinstance(json_resp, dict) else 'not dict'}")
                        data = extract_data(json_resp)
                        print(f"[vManage] GET extracted data length: {len(data)}")
                        if data and len(data) > 0:
                            print(f"[vManage] GET sample data point keys: {list(data[0].keys()) if data[0] else 'empty'}")
                            return {
                                "success": True,
                                "data": data,
                                "count": len(data),
                                "source_endpoint": "statistics/interface GET",
                                "current_tenant_id": self.current_tenant_id,
                                "timestamp": datetime.now().isoformat()
                            }
                        else:
                            print(f"[vManage] GET returned empty data array")
                    else:
                        print(f"[vManage] GET failed with body: {resp.text[:200]}...")
                        errors.append(f"GET HTTP {resp.status_code} params={list(p.keys())}")
                except Exception as e1:
                    print(f"[vManage] GET exception: {e1}")
                    errors.append(f"GET exception {e1}")

            # 2) Try POST with vManage format based on successful unfiltered query
            # From logs we see the data has fields: vdevice_name, host_name, interface, rx_kbps, tx_kbps
            
            device_fields = ["vdevice_name", "host_name"]  # These appear in the actual data
            iface_fields = ["interface"] if interface else []
            
            for df in device_fields:
                # First try: simple device filter only
                queries_to_try = []
                
                # Query 1: Just device filter
                queries_to_try.append({
                    "query": {
                        "condition": "AND",
                        "rules": [
                            {
                                "field": df,
                                "type": "string",
                                "operator": "equal", 
                                "value": str(device_ip)
                            }
                        ]
                    }
                })
                
                # Query 2: Device + interface filter (if interface specified)
                if interface:
                    queries_to_try.append({
                        "query": {
                            "condition": "AND", 
                            "rules": [
                                {
                                    "field": df,
                                    "type": "string",
                                    "operator": "equal",
                                    "value": str(device_ip)
                                },
                                {
                                    "field": "interface", 
                                    "type": "string",
                                    "operator": "equal",
                                    "value": str(interface)
                                }
                            ]
                        }
                    })
                # Try each query variation
                for i, test_body in enumerate(queries_to_try):
                    try:
                        print(f"[vManage] POST interface stats field={df} query={i+1}/{len(queries_to_try)}")
                        print(f"[vManage] POST body: {test_body}")
                        resp = self.session.post(base, json=test_body, verify=False)
                        print(f"[vManage] POST response status: {resp.status_code}")
                        if resp.status_code == 200:
                            json_resp = resp.json()
                            print(f"[vManage] POST response keys: {list(json_resp.keys()) if isinstance(json_resp, dict) else 'not dict'}")
                            data = extract_data(json_resp)
                            print(f"[vManage] POST extracted data length: {len(data)}")
                            if data and len(data) > 0:
                                print(f"[vManage] POST sample data point keys: {list(data[0].keys()) if data[0] else 'empty'}")
                                return {
                                    "success": True,
                                    "data": data,
                                    "count": len(data),
                                    "source_endpoint": f"statistics/interface POST {df}",
                                    "current_tenant_id": self.current_tenant_id,
                                    "timestamp": datetime.now().isoformat()
                                }
                            else:
                                print(f"[vManage] POST returned empty data array")
                        else:
                            print(f"[vManage] POST failed with body: {resp.text[:200]}...")
                            errors.append(f"POST HTTP {resp.status_code} field={df}")
                    except Exception as e2:
                        print(f"[vManage] POST exception: {e2}")
                        errors.append(f"POST exception {e2} field={df}")

            # 2.5) Try unfiltered query and filter client-side as fallback
            try:
                print(f"[vManage] Trying unfiltered query with client-side filtering...")
                print(f"[vManage] Attempted interval was: {api_interval}")
                unfiltered_body = {"query": {"condition": "AND", "rules": []}}
                resp = self.session.post(base, json=unfiltered_body, verify=False)
                print(f"[vManage] Unfiltered response status: {resp.status_code}")
                if resp.status_code == 200:
                    json_resp = resp.json()
                    all_data = extract_data(json_resp)
                    print(f"[vManage] Unfiltered data length: {len(all_data)}")
                    if all_data and len(all_data) > 0:
                        print(f"[vManage] Unfiltered sample keys: {list(all_data[0].keys())}")
                        
                        # Client-side filtering by device IP, interface, and time range
                        filtered_data = []
                        device_match_fields = ['vdevice_name', 'host_name', 'vmanage_system_ip']
                        
                        # Debug: show sample data for device matching
                        if len(all_data) > 0:
                            sample = all_data[0]
                            sample_device_values = {field: sample.get(field) for field in device_match_fields}
                            print(f"[vManage] Looking for device_ip: {device_ip}")
                            print(f"[vManage] Sample device field values: {sample_device_values}")
                        
                        for item in all_data:
                            # Check if device matches
                            device_match = False
                            for field in device_match_fields:
                                if field in item and str(item[field]) == str(device_ip):
                                    device_match = True
                                    break
                            
                            if device_match:
                                # Skip time range filter for now - use all data for the device
                                time_match = True
                                
                                if time_match:
                                    # Check interface filter if specified
                                    if interface:
                                        if 'interface' in item and str(item['interface']) == str(interface):
                                            filtered_data.append(item)
                                    else:
                                        filtered_data.append(item)
                        
                        print(f"[vManage] Client-side filtered data length: {len(filtered_data)}")
                        if filtered_data:
                            print(f"[vManage] Returning client-side filtered data")
                            return {
                                "success": True,
                                "data": filtered_data,
                                "count": len(filtered_data),
                                "source_endpoint": "statistics/interface POST (client-filtered)",
                                "current_tenant_id": self.current_tenant_id,
                                "timestamp": datetime.now().isoformat()
                            }
            except Exception as e:
                print(f"[vManage] Unfiltered query exception: {e}")

            # 3) All fallback methods attempted above

            return {
                "success": True,
                "data": [],
                "count": 0,
                "note": "Interface statistics query returned no data; tried multiple parameter variants",
                "attempts": errors,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting interface statistics: {str(e)}"
            }

    def get_tloc_statistics(self, device_ip: Optional[str] = None, color: Optional[str] = None, time_range: str = "last 1 hour", interval: str = "5min") -> Dict:
        """
        Get TLOC statistics with multiple endpoint fallbacks.
        Common endpoints include /statistics/tloc and /statistics/approute/tloc.
        Filters by device_ip and/or color when provided.
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result

        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id:
            if 'VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers:
                self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            endpoints = [
                {"url": f"{self.base_url}/statistics/tloc", "name": "statistics/tloc"},
                {"url": f"{self.base_url}/statistics/approute/tloc", "name": "statistics/approute/tloc"},
                {"url": f"{self.base_url}/statistics/approute/tlocpath", "name": "statistics/approute/tlocpath"},
            ]

            errors = []
            for ep in endpoints:
                # Try GET first
                params = {k: v for k, v in {
                    "deviceId": device_ip,
                    "systemIp": device_ip,
                    "color": color,
                    "timeRange": time_range,
                    "interval": interval,
                }.items() if v}
                try:
                    print(f"[vManage] Trying {ep['name']} GET for TLOC stats: {ep['url']}")
                    r = self.session.get(ep["url"], params=params, verify=False)
                    print(f"[vManage] {ep['name']} GET -> HTTP {r.status_code}")
                    if r.status_code == 200:
                        payload = r.json()
                        data = payload.get('data', []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
                        if data:
                            return {
                                "success": True,
                                "data": data,
                                "count": len(data) if isinstance(data, list) else 1,
                                "source_endpoint": f"{ep['name']} GET",
                                "current_tenant_id": self.current_tenant_id,
                                "timestamp": datetime.now().isoformat()
                            }
                    else:
                        errors.append(f"{ep['name']} GET HTTP {r.status_code}")
                except Exception as e1:
                    errors.append(f"{ep['name']} GET exception {e1}")

                # Try POST with simple query DSL
                try:
                    query_rules = list(filter(None, [
                        {"field": "device_ip", "type": "string", "operator": "equal", "value": device_ip} if device_ip else None,
                        {"field": "color", "type": "string", "operator": "equal", "value": color} if color else None,
                    ]))
                    post_body = {
                        "query": {"condition": "AND", "rules": query_rules},
                        "timeRange": {"timeRange": time_range},
                        "interval": interval
                    }
                    print(f"[vManage] Trying {ep['name']} POST for TLOC stats: {ep['url']}")
                    r2 = self.session.post(ep["url"], json=post_body, verify=False)
                    print(f"[vManage] {ep['name']} POST -> HTTP {r2.status_code}")
                    if r2.status_code == 200:
                        payload2 = r2.json()
                        data2 = payload2.get('data', []) if isinstance(payload2, dict) else (payload2 if isinstance(payload2, list) else [])
                        return {
                            "success": True,
                            "data": data2,
                            "count": len(data2) if isinstance(data2, list) else (1 if data2 else 0),
                            "source_endpoint": f"{ep['name']} POST",
                            "current_tenant_id": self.current_tenant_id,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        errors.append(f"{ep['name']} POST HTTP {r2.status_code}")
                except Exception as e2:
                    errors.append(f"{ep['name']} POST exception {e2}")

            return {
                "success": False,
                "error": "Failed to retrieve TLOC statistics",
                "attempts": errors
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting TLOC statistics: {str(e)}"
            }

    def get_control_status(self, device_ip: str) -> Dict:
        """Retrieve control connection status for a device.
        Uses /device/control/synced/connections?deviceId=<system-ip>
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id and ('VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers):
            self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            url = f"{self.base_url}/device/control/synced/connections"
            r = self.session.get(url, params={"deviceId": device_ip}, verify=False)
            if r.status_code == 200:
                payload = r.json()
                data = payload.get('data', []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
                return {"success": True, "data": data, "count": len(data) if isinstance(data, list) else 0}
            return {"success": False, "error": f"HTTP {r.status_code}", "response": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_device_counters(self, device_ip: str) -> Dict:
        """Retrieve device counters (OMP peers, controller connections, BFD sessions).
        Uses /device/counters?deviceId=<system-ip>
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id and ('VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers):
            self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            url = f"{self.base_url}/device/counters"
            r = self.session.get(url, params={"deviceId": device_ip}, verify=False)
            if r.status_code == 200:
                payload = r.json()
                return {"success": True, "data": payload.get('data', payload), "timestamp": datetime.now().isoformat()}
            return {"success": False, "error": f"HTTP {r.status_code}", "response": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_system_status(self, device_ip: str) -> Dict:
        """Retrieve system status for a device.
        Uses /device/system/status?deviceId=<system-ip>
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id and ('VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers):
            self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            url = f"{self.base_url}/device/system/status"
            r = self.session.get(url, params={"deviceId": device_ip}, verify=False)
            if r.status_code == 200:
                payload = r.json()
                return {"success": True, "data": payload.get('data', payload), "timestamp": datetime.now().isoformat()}
            return {"success": False, "error": f"HTTP {r.status_code}", "response": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_approute_aggregation(self,
                                  local_system_ip: Optional[str] = None,
                                  remote_system_ip: Optional[str] = None,
                                  last_n_hours: Optional[int] = 1,
                                  start_time_ms: Optional[int] = None,
                                  end_time_ms: Optional[int] = None,
                                  histogram_hours: int = 24) -> Dict:
        """Aggregation API for Application Aware Routing (latency/loss/jitter/vQoE).
        Uses /statistics/approute/fec/aggregation with either last_n_hours or explicit between.
        """
        if not self.authenticated:
            auth_result = self.authenticate()
            if not auth_result["success"]:
                return auth_result
        if self.session_id and 'session-id' not in self.session.headers:
            self.session.headers['session-id'] = self.session_id
        if self.current_tenant_id and ('VSessionId' not in self.session.headers and 'X-Tenant-Id' not in self.session.headers):
            self.session.headers['X-Tenant-Id'] = self.current_tenant_id

        try:
            url = f"{self.base_url}/statistics/approute/fec/aggregation"
            # Build query rules
            rules = []
            if start_time_ms and end_time_ms:
                rules.append({"value": [start_time_ms, end_time_ms], "field": "entry_time", "type": "date", "operator": "between"})
            else:
                rules.append({"value": [str(last_n_hours or 1)], "field": "entry_time", "type": "date", "operator": "last_n_hours"})
            if local_system_ip:
                rules.append({"value": [local_system_ip], "field": "local_system_ip", "type": "string", "operator": "in"})
            if remote_system_ip:
                rules.append({"value": [remote_system_ip], "field": "remote_system_ip", "type": "string", "operator": "in"})

            body = {
                "query": {"condition": "AND", "rules": rules},
                "aggregation": {
                    "field": [
                        {"property": "name", "sequence": 1, "size": 6000}
                    ],
                    "metrics": [
                        {"property": "loss_percentage", "type": "avg"},
                        {"property": "vqoe_score", "type": "avg"},
                        {"property": "latency", "type": "avg"},
                        {"property": "jitter", "type": "avg"}
                    ]
                }
            }

            # If histogram requested (e.g., per 24 hours)
            if histogram_hours and histogram_hours > 0:
                body["aggregation"]["histogram"] = {"property": "entry_time", "type": "hour", "interval": histogram_hours, "order": "asc"}

            r = self.session.post(url, json=body, verify=False)
            if r.status_code == 200:
                payload = r.json()
                data = payload.get('data', payload)
                return {"success": True, "data": data, "timestamp": datetime.now().isoformat(), "query": body}
            return {"success": False, "error": f"HTTP {r.status_code}", "response": r.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close(self):
        """
        Close the session
        """
        if self.session:
            self.session.close()
        self.authenticated = False

# Test function
if __name__ == "__main__":
    # Example usage
    client = VManageClient(
        host="36.67.62.248", 
        username="admin", 
        password="admin"
    )
    
    # Test authentication
    auth_result = client.authenticate()
    print("Authentication:", auth_result)
    
    if auth_result["success"]:
        # Test get devices
        devices_result = client.get_devices()
        print("Devices:", devices_result)
    
    client.close()