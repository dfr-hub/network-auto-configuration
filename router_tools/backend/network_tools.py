import subprocess
import json
import re
import platform
from datetime import datetime
from typing import Dict, List, Optional

class NetworkTools:
    def __init__(self):
        self.os_type = platform.system().lower()
    
    def _get_timestamp(self):
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
    
    def ping(self, host: str, count: int = 4) -> Dict:
        """
        Melakukan ping ke host target
        """
        try:
            # Command berbeda untuk Windows dan Linux/Mac
            if self.os_type == "windows":
                cmd = ["ping", "-n", str(count), host]
            else:
                cmd = ["ping", "-c", str(count), host]
            
            # Jalankan command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Parse hasil ping
            ping_data = self._parse_ping_output(result.stdout, result.stderr, result.returncode)
            ping_data["command"] = " ".join(cmd)
            ping_data["timestamp"] = datetime.now().isoformat()
            ping_data["host"] = host
            
            return ping_data
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Ping timeout after 30 seconds",
                "host": host,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "host": host,
                "timestamp": datetime.now().isoformat()
            }
    
    def traceroute(self, host: str, max_hops: int = 30) -> Dict:
        """
        Melakukan traceroute ke host target
        """
        try:
            # Command berbeda untuk Windows dan Linux/Mac
            if self.os_type == "windows":
                cmd = ["tracert", "-h", str(max_hops), host]
            else:
                cmd = ["traceroute", "-m", str(max_hops), host]
            
            # Jalankan command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse hasil traceroute
            trace_data = self._parse_traceroute_output(result.stdout, result.stderr, result.returncode)
            trace_data["command"] = " ".join(cmd)
            trace_data["timestamp"] = datetime.now().isoformat()
            trace_data["host"] = host
            
            return trace_data
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Traceroute timeout after 60 seconds",
                "host": host,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "host": host,
                "timestamp": datetime.now().isoformat()
            }
    
    def _parse_ping_output(self, stdout: str, stderr: str, returncode: int) -> Dict:
        """
        Parse output ping untuk Windows dan Linux
        """
        if returncode != 0:
            return {
                "success": False,
                "error": stderr or "Ping failed",
                "raw_output": stdout
            }
        
        # Parsing untuk Windows
        if self.os_type == "windows":
            return self._parse_windows_ping(stdout)
        else:
            return self._parse_unix_ping(stdout)
    
    def _parse_windows_ping(self, output: str) -> Dict:
        """
        Parse output ping Windows
        """
        lines = output.split('\n')
        packets_sent = 0
        packets_received = 0
        packet_loss = 0
        min_time = None
        max_time = None
        avg_time = None
        replies = []
        
        try:
            # Cari statistik packet
            for line in lines:
                if "Packets: Sent =" in line:
                    # Format: Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
                    sent_match = re.search(r'Sent = (\d+)', line)
                    received_match = re.search(r'Received = (\d+)', line)
                    loss_match = re.search(r'Lost = (\d+)', line)
                    
                    if sent_match:
                        packets_sent = int(sent_match.group(1))
                    if received_match:
                        packets_received = int(received_match.group(1))
                    if loss_match:
                        packet_loss = int(loss_match.group(1))
                
                # Parse individual replies
                if "Reply from" in line and "time=" in line:
                    time_match = re.search(r'time=(\d+)ms', line)
                    if time_match:
                        reply_time = int(time_match.group(1))
                        replies.append(reply_time)
                
                # Parse timing statistics
                if "Minimum =" in line:
                    # Format: Minimum = 1ms, Maximum = 4ms, Average = 2ms
                    min_match = re.search(r'Minimum = (\d+)ms', line)
                    max_match = re.search(r'Maximum = (\d+)ms', line)
                    avg_match = re.search(r'Average = (\d+)ms', line)
                    
                    if min_match:
                        min_time = int(min_match.group(1))
                    if max_match:
                        max_time = int(max_match.group(1))
                    if avg_match:
                        avg_time = int(avg_match.group(1))
            
            return {
                "success": True,
                "packets_sent": packets_sent,
                "packets_received": packets_received,
                "packet_loss": packet_loss,
                "packet_loss_percent": (packet_loss / packets_sent * 100) if packets_sent > 0 else 0,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "avg_time_ms": avg_time,
                "replies": replies,
                "raw_output": output
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse ping output: {str(e)}",
                "raw_output": output
            }
    
    def _parse_unix_ping(self, output: str) -> Dict:
        """
        Parse output ping Unix/Linux/Mac
        """
        lines = output.split('\n')
        packets_sent = 0
        packets_received = 0
        packet_loss_percent = 0
        min_time = None
        max_time = None
        avg_time = None
        replies = []
        
        try:
            for line in lines:
                # Parse individual replies
                if "bytes from" in line and "time=" in line:
                    time_match = re.search(r'time=([0-9.]+)', line)
                    if time_match:
                        reply_time = float(time_match.group(1))
                        replies.append(reply_time)
                
                # Parse packet statistics
                if "packets transmitted" in line:
                    # Format: 4 packets transmitted, 4 received, 0% packet loss
                    sent_match = re.search(r'(\d+) packets transmitted', line)
                    received_match = re.search(r'(\d+) received', line)
                    loss_match = re.search(r'(\d+)% packet loss', line)
                    
                    if sent_match:
                        packets_sent = int(sent_match.group(1))
                    if received_match:
                        packets_received = int(received_match.group(1))
                    if loss_match:
                        packet_loss_percent = int(loss_match.group(1))
                
                # Parse timing statistics
                if "min/avg/max" in line:
                    # Format: round-trip min/avg/max/stddev = 1.234/2.345/3.456/0.789 ms
                    time_match = re.search(r'= ([0-9.]+)/([0-9.]+)/([0-9.]+)', line)
                    if time_match:
                        min_time = float(time_match.group(1))
                        avg_time = float(time_match.group(2))
                        max_time = float(time_match.group(3))
            
            return {
                "success": True,
                "packets_sent": packets_sent,
                "packets_received": packets_received,
                "packet_loss": packets_sent - packets_received,
                "packet_loss_percent": packet_loss_percent,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "avg_time_ms": avg_time,
                "replies": replies,
                "raw_output": output
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse ping output: {str(e)}",
                "raw_output": output
            }
    
    def _parse_traceroute_output(self, stdout: str, stderr: str, returncode: int) -> Dict:
        """
        Parse output traceroute untuk Windows dan Linux
        """
        if returncode != 0:
            return {
                "success": False,
                "error": stderr or "Traceroute failed",
                "raw_output": stdout
            }
        
        # Parsing untuk Windows (tracert) dan Linux (traceroute)
        if self.os_type == "windows":
            return self._parse_windows_tracert(stdout)
        else:
            return self._parse_unix_traceroute(stdout)
    
    def _parse_windows_tracert(self, output: str) -> Dict:
        """
        Parse output tracert Windows
        """
        lines = output.split('\n')
        hops = []
        
        try:
            for line in lines:
                line = line.strip()
                if not line or "Tracing route" in line or "over a maximum" in line:
                    continue
                
                # Format Windows tracert:
                # 1    <1 ms    <1 ms    <1 ms  192.168.1.1
                # 2     1 ms     1 ms     1 ms  10.0.0.1
                hop_match = re.match(r'^\s*(\d+)\s+(.+)', line)
                if hop_match:
                    hop_num = int(hop_match.group(1))
                    hop_data = hop_match.group(2).strip()
                    
                    # Parse timing and hostname/IP
                    times = []
                    hostname = ""
                    
                    # Look for timing patterns like "1 ms", "<1 ms", "* ms"
                    time_parts = re.findall(r'([<*]?\d+\s+ms|\*)', hop_data)
                    for time_part in time_parts:
                        if time_part == '*':
                            times.append("*")
                        else:
                            times.append(time_part)
                    
                    # Get hostname/IP (last part after times)
                    parts = hop_data.split()
                    if len(parts) > 3:
                        hostname = parts[-1]
                    
                    hops.append({
                        "hop": hop_num,
                        "hostname": hostname,
                        "times": times[:3],  # Take first 3 times
                        "raw_line": line
                    })
            
            return {
                "success": True,
                "hops": hops,
                "total_hops": len(hops),
                "raw_output": output
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse tracert output: {str(e)}",
                "raw_output": output
            }
    
    def _parse_unix_traceroute(self, output: str) -> Dict:
        """
        Parse output traceroute Unix/Linux/Mac
        """
        lines = output.split('\n')
        hops = []
        
        try:
            for line in lines:
                line = line.strip()
                if not line or "traceroute to" in line:
                    continue
                
                # Format Unix traceroute:
                # 1  192.168.1.1 (192.168.1.1)  0.234 ms  0.198 ms  0.187 ms
                # 2  * * *
                hop_match = re.match(r'^\s*(\d+)\s+(.+)', line)
                if hop_match:
                    hop_num = int(hop_match.group(1))
                    hop_data = hop_match.group(2).strip()
                    
                    times = []
                    hostname = ""
                    
                    if "* * *" in hop_data:
                        times = ["*", "*", "*"]
                        hostname = "*"
                    else:
                        # Extract hostname
                        hostname_match = re.match(r'^([^\s]+)', hop_data)
                        if hostname_match:
                            hostname = hostname_match.group(1)
                        
                        # Extract times
                        time_matches = re.findall(r'(\d+\.?\d*)\s+ms', hop_data)
                        times = [f"{t} ms" for t in time_matches]
                    
                    hops.append({
                        "hop": hop_num,
                        "hostname": hostname,
                        "times": times,
                        "raw_line": line
                    })
            
            return {
                "success": True,
                "hops": hops,
                "total_hops": len(hops),
                "raw_output": output
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse traceroute output: {str(e)}",
                "raw_output": output
            }

# Test function
if __name__ == "__main__":
    tools = NetworkTools()
    
    # Test ping
    print("Testing ping to google.com...")
    ping_result = tools.ping("google.com", 4)
    print(json.dumps(ping_result, indent=2))
    
    print("\n" + "="*50 + "\n")
    
    # Test traceroute
    print("Testing traceroute to google.com...")
    trace_result = tools.traceroute("google.com", 10)
    print(json.dumps(trace_result, indent=2))