import paramiko
import time
import socket
from typing import Dict, List, Optional, Union
from datetime import datetime
import re
import json
from ssh_helper import SSHCommandHandler

class RouterConnection:
    """
    Base class untuk koneksi router via SSH
    """
    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.ssh_client = None
        self.shell = None
        self.connected = False
        self.device_type = "unknown"
        self.prompt = None
        self.last_activity = None
        self.keepalive_interval = 30  # seconds
        
    def connect(self, timeout: int = 30) -> Dict:
        """
        Koneksi SSH ke router
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.ssh_client.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=timeout
            )

            # Set keepalive on transport (some devices close idle channels)
            try:
                transport = self.ssh_client.get_transport()
                if transport:
                    transport.set_keepalive(self.keepalive_interval)
            except Exception as _:
                pass
            
            # Buat interactive shell
            self.shell = self.ssh_client.invoke_shell()
            time.sleep(2)  # Wait for shell to initialize
            
            # Clear initial output
            self.shell.recv(4096)
            
            # Detect device type
            self._detect_device_type()
            # Detect prompt after device type known
            self._detect_prompt()
            
            self.connected = True
            self.last_activity = time.time()
            return {
                "success": True,
                "message": f"Connected to {self.host}",
                "device_type": self.device_type,
                "timestamp": datetime.now().isoformat()
            }
            
        except paramiko.AuthenticationException:
            return {
                "success": False,
                "error": "Authentication failed - check username/password",
                "timestamp": datetime.now().isoformat()
            }
        except paramiko.SSHException as e:
            return {
                "success": False,
                "error": f"SSH connection error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        except socket.timeout:
            return {
                "success": False,
                "error": f"Connection timeout to {self.host}:{self.port}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def disconnect(self):
        """
        Tutup koneksi SSH
        """
        if self.shell:
            self.shell.close()
        if self.ssh_client:
            self.ssh_client.close()
        self.connected = False
    
    def _detect_device_type(self):
        """
        Deteksi jenis router berdasarkan banner/prompt
        """
        try:
            # Clear any existing output
            while self.shell.recv_ready():
                self.shell.recv(4096)
            
            # Send show version untuk deteksi lebih akurat
            self.shell.send("show version\n")
            time.sleep(5)  # Wait longer for command completion
            
            version_output = ""
            max_attempts = 10
            attempts = 0
            
            while attempts < max_attempts:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(4096).decode('utf-8', errors='ignore')
                    version_output += chunk
                    attempts = 0  # Reset if we're still receiving data
                else:
                    attempts += 1
                    time.sleep(0.5)
            
            print(f"Detection output: {version_output[:500]}...")  # Debug output
            
            # Improved detection logic
            version_upper = version_output.upper()
            
            # Check for Cisco devices first (most common)
            if any(prompt in version_output for prompt in ["#", ">"]):
                
                # Deteksi Cisco IOS XE (prioritas tinggi)
                ios_xe_keywords = [
                    "IOS XE", "IOS-XE", "IOSXE", "CATALYST L3 SWITCH", 
                    "CAT9K", "CAT3K", "C9300", "C9200", "C9400", "C9500",
                    "C3850", "C3650", "CSR1000V", "ISR4", "ASR1000", 
                    "CISCO NEXUS", "NX-OS"
                ]
                
                if any(keyword in version_upper for keyword in ios_xe_keywords):
                    self.device_type = "cisco_ios_xe"
                    print(f"Detected as Cisco IOS XE")
                    return
                
                # Deteksi Cisco IOS tradisional
                ios_keywords = [
                    "CISCO IOS", "IOS SOFTWARE", "INTERNETWORK OPERATING SYSTEM",
                    "C2960", "C3560", "C2950", "C1900", "C2900", "C800", "C1800",
                    "CISCO ROUTER", "CISCO SWITCH"
                ]
                
                if any(keyword in version_upper for keyword in ios_keywords):
                    self.device_type = "cisco_ios"
                    print(f"Detected as Cisco IOS")
                    return
                
                # Deteksi berdasarkan command response pattern
                if "CISCO" in version_upper and ("SOFTWARE" in version_upper or "VERSION" in version_upper):
                    # Default ke IOS XE untuk device modern
                    self.device_type = "cisco_ios_xe"
                    print(f"Detected as Cisco IOS XE (default modern)")
                    return
            
            # Deteksi vendor lain
            if "MIKROTIK" in version_upper or "] >" in version_output:
                self.device_type = "mikrotik"
            elif any(keyword in version_upper for keyword in ["HUAWEI", "VRP", "QUIDWAY"]):
                self.device_type = "huawei"  
            elif any(keyword in version_upper for keyword in ["JUNIPER", "JUNOS"]):
                self.device_type = "juniper"
            elif any(prompt in version_output for prompt in ["#", ">"]):
                # Jika ada prompt tapi tidak terdeteksi, assume Cisco IOS XE
                self.device_type = "cisco_ios_xe"
                print(f"Unknown Cisco device, defaulting to IOS XE")
            else:
                self.device_type = "generic"
                print(f"Could not detect device type, using generic")
                
        except Exception as e:
            print(f"Device detection error: {e}")
            # Default to cisco_ios_xe for better compatibility
            self.device_type = "cisco_ios_xe"

    def _detect_prompt(self):
        """Attempt to learn the current CLI prompt so we know when a command finishes."""
        try:
            # Send an empty newline, read a short chunk
            self.shell.send("\r")
            time.sleep(0.3)
            buf = ""
            while self.shell.recv_ready():
                buf += self.shell.recv(1024).decode('utf-8', errors='ignore')
            # Heuristic: prompt ends with one of ['#','>'] and last non-empty line
            for line in reversed(buf.splitlines()):
                line = line.strip()
                if not line:
                    continue
                if line.endswith('#') or line.endswith('>'):
                    self.prompt = line
                    break
        except Exception as _:
            pass

    def _ensure_connected(self):
        if not self.connected or not self.ssh_client:
            raise RuntimeError("SSH session not connected")
        transport = self.ssh_client.get_transport()
        if not transport or not transport.is_active():
            raise RuntimeError("SSH transport inactive")
        if not self.shell:
            raise RuntimeError("SSH shell channel missing")

    def _read_until_quiet(self, quiet_time=0.4, max_total=5.0):
        """Read from shell until no new data for quiet_time or until max_total reached."""
        data = ""
        start = time.time()
        last = time.time()
        while True:
            if self.shell.recv_ready():
                chunk = self.shell.recv(4096).decode('utf-8', errors='ignore')
                data += chunk
                last = time.time()
            if (time.time() - last) >= quiet_time:
                break
            if (time.time() - start) >= max_total:
                break
            time.sleep(0.05)
        return data

    def _looks_like_prompt(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return False
        return line.endswith('#') or line.endswith('>')
    
    def send_command(self, command: str, wait_time: int = 2) -> Dict:
        """
        Kirim command ke router dan ambil output
        """
        if not self.connected or not self.shell:
            return {
                "success": False,
                "error": "Not connected to router",
                "command": command
            }
        
        try:
            self._ensure_connected()
            command_clean = command.strip()

            # Quick no-op keepalive if idle
            now = time.time()
            if self.last_activity and now - self.last_activity > self.keepalive_interval:
                try:
                    self.shell.send("\r")
                    self._read_until_quiet(quiet_time=0.2, max_total=1.0)
                except Exception:
                    pass

            # Flush residual
            self._read_until_quiet(quiet_time=0.15, max_total=0.8)

            # Send command (prepend CR to ensure at line start)
            self.shell.send(("\r" + command_clean + "\r").encode('utf-8'))

            raw_output = self._read_until_quiet(quiet_time=0.5, max_total=max(3.0, wait_time))

            # If echo seems missing first char, retry once
            first_line = next((l for l in raw_output.splitlines() if l.strip()), "")
            if command_clean not in first_line and command_clean[1:] in first_line:
                self.shell.send(("\r" + command_clean + "\r").encode('utf-8'))
                raw_output += self._read_until_quiet(quiet_time=0.5, max_total=2.0)

            # Cleaning
            cleaned = []
            seen_echo = False
            for line in raw_output.splitlines():
                li = line.rstrip('\r').strip()
                if not li:
                    continue
                if not seen_echo and (li == command_clean or li.endswith(command_clean) or command_clean in li or command_clean[1:] in li):
                    seen_echo = True
                    continue
                if self._looks_like_prompt(li):
                    # update prompt cache
                    if self.prompt is None:
                        self.prompt = li
                    continue
                cleaned.append(li)
            output = '\n'.join(cleaned).strip()
            self.last_activity = time.time()
            
            # Log success status only
            print(f"✅ Command successful: '{command}' on {self.host}")
            
            return {
                "success": True,
                "command": command,
                "output": output,
                "timestamp": datetime.now().isoformat(),
                "device_type": self.device_type
            }
            
        except Exception as e:
            # Log failure status only
            print(f"❌ Command failed: '{command}' on {self.host} - Error: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "command": command,
                "timestamp": datetime.now().isoformat()
            }
    
    def send_config_commands(self, commands: List[str]) -> Dict:
        """
        Kirim multiple commands untuk konfigurasi
        """
        if not isinstance(commands, list):
            commands = [commands]
        
        results = []
        
        # Enter config mode berdasarkan device type
        if self.device_type in ["cisco_ios", "cisco_ios_xe"]:
            config_mode = "configure terminal"
        elif self.device_type == "mikrotik":
            config_mode = ""  # MikroTik tidak perlu config mode
        elif self.device_type == "huawei":
            config_mode = "system-view"
        else:
            config_mode = "configure terminal"  # Default
        
        # Enter config mode
        if config_mode:
            result = self.send_command(config_mode)
            results.append(result)
        
        # Send each command
        for cmd in commands:
            result = self.send_command(cmd)
            results.append(result)
        
        # Exit config mode
        if self.device_type in ["cisco_ios", "cisco_ios_xe"]:
            exit_cmd = "end"
        elif self.device_type == "huawei":
            exit_cmd = "quit"
        else:
            exit_cmd = "exit"
        
        if config_mode:
            result = self.send_command(exit_cmd)
            results.append(result)
        
        return {
            "success": True,
            "commands": commands,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

class RouterManager:
    """
    Manager untuk multiple router connections dan operasi
    """
    def __init__(self):
        self.connections = {}
        self.command_templates = {
            "cisco_ios": {
                "show_version": "show version",
                "show_running": "show running-config",
                "show_interfaces": "show ip interface brief",
                "show_routes": "show ip route",
                "show_arp": "show arp",
                "show_mac": "show mac address-table",
                "show_log": "show logging",
                "show_inventory": "show inventory",
                "show_processes": "show processes cpu",
                "show_memory": "show memory",
                "show_uptime": "show version | include uptime"
            },
            "cisco_ios_xe": {
                "show_version": "show version",
                "show_running": "show running-config",
                "show_interfaces": "show ip interface brief",
                "show_routes": "show ip route",
                "show_arp": "show arp",
                "show_mac": "show mac address-table",
                "show_log": "show logging",
                "show_inventory": "show inventory",
                "show_processes": "show processes cpu sorted",
                "show_memory": "show memory statistics",
                "show_platform": "show platform",
                "show_environment": "show environment all",
                "show_redundancy": "show redundancy",
                "show_stackwise": "show switch",
                "show_license": "show license summary",
                "show_boot": "show boot",
                "show_flash": "show flash:",
                "show_interfaces_status": "show interfaces status",
                "show_interfaces_description": "show interfaces description",
                "show_vlan": "show vlan brief",
                "show_spanning_tree": "show spanning-tree summary",
                "show_cdp_neighbors": "show cdp neighbors detail",
                "show_lldp_neighbors": "show lldp neighbors detail",
                "show_etherchannel": "show etherchannel summary",
                "show_hsrp": "show standby brief",
                "show_vrf": "show vrf",
                "show_bgp": "show ip bgp summary",
                "show_ospf": "show ip ospf neighbor",
                "show_eigrp": "show ip eigrp neighbors",
                "show_nat": "show ip nat translations",
                "show_access_lists": "show access-lists",
                "show_route_map": "show route-map",
                "show_policy_map": "show policy-map",
                "show_qos": "show policy-map interface",
                "show_crypto": "show crypto session",
                "show_vpn": "show crypto isakmp sa",
                "show_users": "show users",
                "show_sessions": "show sessions",
                "show_clock": "show clock",
                "show_ntp": "show ntp status"
            },
            "generic": {
                "show_version": "show version",
                "show_running": "show running-config",
                "show_interfaces": "show ip interface brief",
                "show_routes": "show ip route",
                "show_arp": "show arp",
                "show_mac": "show mac address-table",
                "show_log": "show logging",
                "show_inventory": "show inventory",
                "show_processes": "show processes cpu",
                "show_memory": "show memory",
                "show_platform": "show platform",
                "show_environment": "show environment all"
            },
            "mikrotik": {
                "show_version": "/system resource print",
                "show_running": "/export compact",
                "show_interfaces": "/interface print",
                "show_routes": "/ip route print",
                "show_arp": "/ip arp print",
                "show_mac": "/interface bridge host print",
                "show_log": "/log print"
            },
            "huawei": {
                "show_version": "display version",
                "show_running": "display current-configuration",
                "show_interfaces": "display ip interface brief",
                "show_routes": "display ip routing-table",
                "show_arp": "display arp",
                "show_mac": "display mac-address",
                "show_log": "display logbuffer"
            }
        }
    
    def add_router(self, name: str, host: str, username: str, password: str, port: int = 22, device_type: str = None) -> Dict:
        """
        Tambah router ke manager
        """
        try:
            router = RouterConnection(host, username, password, port)
            connection_result = router.connect()
            
            if connection_result["success"]:
                # Override device type jika manual setting diberikan
                if device_type and device_type in self.command_templates:
                    router.device_type = device_type
                    print(f"Device type manually set to: {device_type}")
                
                self.connections[name] = router
                return {
                    "success": True,
                    "message": f"Router {name} added successfully",
                    "device_type": router.device_type,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return connection_result
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def remove_router(self, name: str) -> Dict:
        """
        Hapus router dari manager
        """
        if name in self.connections:
            self.connections[name].disconnect()
            del self.connections[name]
            return {
                "success": True,
                "message": f"Router {name} removed"
            }
        else:
            return {
                "success": False,
                "error": f"Router {name} not found"
            }
    
    def list_routers(self) -> Dict:
        """
        List semua router yang terdaftar dengan status check real-time
        """
        routers = []
        for name, conn in self.connections.items():
            # Check real connection status by testing SSH connection
            is_connected = conn.connected and self._check_connection_alive(conn)
            
            routers.append({
                "name": name,
                "host": conn.host,
                "connected": is_connected,
                "device_type": conn.device_type,
                "username": getattr(conn, 'username', None),
                "port": getattr(conn, 'port', None)
            })
        
        return {
            "success": True,
            "routers": routers,
            "total": len(routers)
        }
    
    def _check_connection_alive(self, connection) -> bool:
        """
        Check if SSH connection is still alive
        """
        try:
            if not connection.ssh_client:
                connection.connected = False
                return False
            transport = connection.ssh_client.get_transport()
            if not transport or not transport.is_active():
                connection.connected = False
                return False
            # Trust existing connected flag if transport active
            connection.connected = True
            return True
        except Exception as e:
            print(f"Connection check failed for {connection.host}: {e}")
            connection.connected = False
            return False
    
    def execute_command(self, router_name: str, command: str) -> Dict:
        """
        Execute command pada router tertentu
        """
        if router_name not in self.connections:
            return {
                "success": False,
                "error": f"Router {router_name} not found"
            }
        
        router = self.connections[router_name]
        if not router.connected:
            # Try to reconnect
            reconnect_result = router.connect()
            if not reconnect_result["success"]:
                return reconnect_result
        
        return router.send_command(command)
    
    def get_router_info(self, router_name: str) -> Dict:
        """
        Ambil informasi dasar router
        """
        if router_name not in self.connections:
            return {
                "success": False,
                "error": f"Router {router_name} not found"
            }
        
        router = self.connections[router_name]
        device_type = router.device_type
        
        if device_type in self.command_templates:
            commands = self.command_templates[device_type]

            # Disable paging first for full output (terminal length 0 etc)
            self._disable_paging(router_name, device_type)
            
            # Get version info
            version_result = self.execute_command(router_name, commands["show_version"])
            interfaces_result = self.execute_command(router_name, commands["show_interfaces"])
            
            return {
                "success": True,
                "router_name": router_name,
                "host": router.host,
                "device_type": device_type,
                "version_info": version_result,
                "interfaces_info": interfaces_result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"Unsupported device type: {device_type}"
            }
    
    def backup_config(self, router_name: str) -> Dict:
        """
        Backup konfigurasi router
        """
        if router_name not in self.connections:
            return {
                "success": False,
                "error": f"Router {router_name} not found"
            }
        
        router = self.connections[router_name]
        device_type = router.device_type
        
        if device_type in self.command_templates:
            show_running_cmd = self.command_templates[device_type]["show_running"]

            # Disable paging to capture full running config
            self._disable_paging(router_name, device_type)
            result = self.execute_command(router_name, show_running_cmd)
            
            if result["success"]:
                # Save to file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{router_name}_config_{timestamp}.txt"
                filepath = f"../logs/{filename}"
                
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(f"# Configuration backup for {router_name}\n")
                        f.write(f"# Host: {router.host}\n")
                        f.write(f"# Device Type: {device_type}\n")
                        f.write(f"# Backup Time: {datetime.now().isoformat()}\n")
                        f.write(f"# Command: {show_running_cmd}\n")
                        f.write("="*50 + "\n\n")
                        f.write(result["output"])
                    
                    return {
                        "success": True,
                        "message": "Configuration backed up successfully",
                        "filename": filename,
                        "filepath": filepath,
                        "router_name": router_name,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to save backup: {str(e)}"
                    }
            else:
                return result
        else:
            return {
                "success": False,
                "error": f"Unsupported device type: {device_type}"
            }
    
    def get_logs(self, router_name: str, log_type: str = "all") -> Dict:
        """
        Ambil log dari router
        log_type: all, system, interface, routing
        """
        if router_name not in self.connections:
            return {
                "success": False,
                "error": f"Router {router_name} not found"
            }
        
        router = self.connections[router_name]
        device_type = router.device_type
        
        if device_type not in self.command_templates:
            return {
                "success": False,
                "error": f"Unsupported device type: {device_type}"
            }
        
        commands = self.command_templates[device_type]
        logs = {}

        # Disable paging once before collecting logs for full outputs
        self._disable_paging(router_name, device_type)
        
        if log_type == "all" or log_type == "system":
            logs["system"] = self.execute_command(router_name, commands["show_log"])
        
        if log_type == "all" or log_type == "interface":
            logs["interfaces"] = self.execute_command(router_name, commands["show_interfaces"])
        
        if log_type == "all" or log_type == "routing":
            logs["routes"] = self.execute_command(router_name, commands["show_routes"])
            logs["arp"] = self.execute_command(router_name, commands["show_arp"])
        
        return {
            "success": True,
            "router_name": router_name,
            "log_type": log_type,
            "logs": logs,
            "timestamp": datetime.now().isoformat()
        }

    def _disable_paging(self, router_name: str, device_type: str):
        """Send the appropriate no-paging / terminal length 0 command if supported.

        This prevents CLI output from being paginated (---More---) so API captures full data.
        """
        paging_cmds = {
            "cisco_ios": "terminal length 0",
            "cisco_ios_xe": "terminal length 0",
            "generic": "terminal length 0",  # Treat generic like Cisco
            "huawei": "screen-length 0 temporary",
            "juniper": "set cli screen-length 0",
            # MikroTik typically doesn't paginate the same way; omit
        }
        cmd = paging_cmds.get(device_type)
        if not cmd:
            return
        try:
            self.execute_command(router_name, cmd)
        except Exception as e:
            print(f"Warning: failed to disable paging on {router_name}: {e}")

# Test function
if __name__ == "__main__":
    # Test RouterManager
    manager = RouterManager()
    
    # Example usage (ganti dengan IP/kredential router Anda)
    print("Testing Router Manager...")
    print("Note: Update IP, username, password sesuai router Anda")
    
    # Example:
    # result = manager.add_router("cisco_r1", "192.168.1.1", "admin", "password")
    # print(json.dumps(result, indent=2))
    
    print("RouterManager initialized successfully")
    print("Available device types:", list(manager.command_templates.keys()))