import socket
from typing import Dict
from datetime import datetime

class PortScanner:
    """
    Simple port scanner untuk test konektivitas
    """
    
    @staticmethod
    def scan_port(host: str, port: int, timeout: int = 5) -> Dict:
        """
        Scan single port pada host
        """
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Try to connect
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                return {
                    "success": True,
                    "host": host,
                    "port": port,
                    "status": "open",
                    "message": f"Port {port} is open on {host}",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "host": host,
                    "port": port,
                    "status": "closed",
                    "message": f"Port {port} is closed on {host}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except socket.gaierror as e:
            return {
                "success": False,
                "host": host,
                "port": port,
                "status": "error",
                "error": f"DNS resolution failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "host": host,
                "port": port,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    @staticmethod
    def scan_common_ports(host: str) -> Dict:
        """
        Scan common ports pada host
        """
        common_ports = [22, 23, 80, 443, 21, 25, 53, 110, 993, 995]
        results = []
        
        for port in common_ports:
            result = PortScanner.scan_port(host, port, timeout=3)
            results.append(result)
        
        open_ports = [r for r in results if r["success"]]
        
        return {
            "success": True,
            "host": host,
            "total_ports": len(common_ports),
            "open_ports": len(open_ports),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

# Test function
if __name__ == "__main__":
    scanner = PortScanner()
    
    # Test specific IP
    host = "36.88.161.170"
    print(f"Testing connectivity to {host}...")
    
    # Test SSH port
    ssh_result = scanner.scan_port(host, 22)
    print(f"SSH Port 22: {ssh_result}")
    
    # Test common ports
    print(f"\nScanning common ports on {host}...")
    scan_result = scanner.scan_common_ports(host)
    
    for result in scan_result["results"]:
        status = "✅ OPEN" if result["success"] else "❌ CLOSED"
        print(f"Port {result['port']}: {status}")