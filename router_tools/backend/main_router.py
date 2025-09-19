from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import time
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network_tools import NetworkTools
from router_manager import RouterManager
from vmanage_client import VManageClient

app = FastAPI(title="Router Management Tools", version="2.0.0")

# Mount static files (frontend)
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Initialize tools
network_tools = NetworkTools()
router_manager = RouterManager()
vmanage_clients = {}  # Store vManage client instances

# Pydantic models untuk request
class PingRequest(BaseModel):
    host: str
    count: Optional[int] = 4

class TracerouteRequest(BaseModel):
    host: str
    max_hops: Optional[int] = 30

class RouterConnectionRequest(BaseModel):
    name: str
    host: str
    username: str
    password: str
    port: Optional[int] = 22
    device_type: Optional[str] = None

class RouterCommandRequest(BaseModel):
    router_name: str
    command: str

class RouterConfigRequest(BaseModel):
    router_name: str
    commands: List[str]

class VManageConnectionRequest(BaseModel):
    name: str
    host: str
    username: str
    password: str
    port: Optional[int] = 443

class VManageDeviceRequest(BaseModel):
    vmanage_name: str
    device_id: Optional[str] = None

class VManageTenantRequest(BaseModel):
    # vmanage_name sebenarnya sudah ada di path; buat optional supaya frontend cukup kirim tenant_id
    vmanage_name: Optional[str] = None
    tenant_id: str

class VManagePingRequest(BaseModel):
    device_ip: str
    target_ip: str
    vpn: str = "0"
    count: int = 5

class VManageTracerouteRequest(BaseModel):
    device_ip: str
    target_ip: str
    vpn: str = "0"

class VManageNslookupRequest(BaseModel):
    device_ip: str
    hostname: str
    vpn: str = "0"
    dns_server: str = "8.8.8.8"

class VManageInterfaceStatsRequest(BaseModel):
    device_ip: str
    interface: Optional[str] = None
    time_range: str = "last 1 hour"
    interval: str = "5min"

class VManageTlocStatsRequest(BaseModel):
    device_ip: Optional[str] = None
    color: Optional[str] = None
    time_range: str = "last 1 hour"
    interval: str = "5min"

class VManageApprouteAggRequest(BaseModel):
    local_system_ip: Optional[str] = None
    remote_system_ip: Optional[str] = None
    last_n_hours: Optional[int] = 1
    start_time_ms: Optional[int] = None
    end_time_ms: Optional[int] = None
    histogram_hours: int = 24

from pathlib import Path

# Root endpoint - serve modern dashboard ONLY
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the modern dashboard (modern_dashboard.html). If not found, return explicit error so kita tahu bukan UI lama."""
    current_dir = Path(__file__).resolve().parent
    dashboard_path = (current_dir / ".." / "frontend" / "modern_dashboard.html").resolve()

    # Logging path info sekali per request (stdout)
    print(f"[ROOT] Request received. Resolved modern_dashboard path: {dashboard_path}")
    print(f"[ROOT] Exists: {dashboard_path.exists()}  Is File: {dashboard_path.is_file()}")

    if not dashboard_path.exists():
        return HTMLResponse(
            content=(
                "<h1>modern_dashboard.html NOT FOUND</h1>"
                f"<p>Dicari di: {dashboard_path}</p>"
                "<p>Pastikan file tersebut ada. Tidak lagi fallback ke router_management.html agar jelas.</p>"
            ),
            status_code=500,
        )

    try:
        content = dashboard_path.read_text(encoding="utf-8")
        # Quick sanity marker injection (komentar) agar saat curl terlihat jelas versi baru
        if "<!-- MODERN DASHBOARD MARKER -->" not in content:
            content = "<!-- MODERN DASHBOARD MARKER -->\n" + content
        return HTMLResponse(content=content)
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Gagal load modern dashboard</h1><pre>{str(e)}</pre>",
            status_code=500,
        )

# ==================== NETWORK TOOLS ENDPOINTS ====================

@app.get("/legacy", response_class=HTMLResponse)
async def legacy_ui():
    """Serve legacy UI (router_management.html) for transitional access."""
    current_dir = Path(__file__).resolve().parent
    legacy_path = (current_dir / ".." / "frontend" / "router_management.html").resolve()
    if not legacy_path.exists():
        return HTMLResponse("<h1>Legacy UI not found</h1>", status_code=404)
    try:
        content = legacy_path.read_text(encoding="utf-8")
        banner = (
            "<!-- LEGACY UI -->\n" \
            "<div style='background:#ffc107;padding:8px;font-size:12px;font-family:Arial;" \
            "border-bottom:1px solid #e0a800;text-align:center;'>" \
            "You are viewing the legacy interface. <a href='/' style='color:#000;font-weight:bold;'>Go to Modern Dashboard</a>" \
            "</div>"
        )
        return HTMLResponse(banner + content)
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading legacy UI</h1><pre>{e}</pre>", status_code=500)

@app.post("/api/ping")
async def ping_host(request: PingRequest):
    """
    Ping a host and return results
    """
    if not request.host:
        raise HTTPException(status_code=400, detail="Host is required")
    
    if request.count < 1 or request.count > 100:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 100")
    
    try:
        result = network_tools.ping(request.host, request.count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/traceroute")
async def traceroute_host(request: TracerouteRequest):
    """
    Traceroute to a host and return results
    """
    if not request.host:
        raise HTTPException(status_code=400, detail="Host is required")
    
    if request.max_hops < 1 or request.max_hops > 64:
        raise HTTPException(status_code=400, detail="Max hops must be between 1 and 64")
    
    try:
        result = network_tools.traceroute(request.host, request.max_hops)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ROUTER MANAGEMENT ENDPOINTS ====================

@app.post("/api/router/connect")
async def connect_router(request: RouterConnectionRequest):
    """
    Connect to router via SSH
    """
    if not all([request.name, request.host, request.username, request.password]):
        raise HTTPException(status_code=400, detail="All fields (name, host, username, password) are required")
    
    try:
        result = router_manager.add_router(
            request.name, 
            request.host, 
            request.username, 
            request.password, 
            request.port,
            request.device_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/router/list")
async def list_routers():
    """
    List all connected routers
    """
    try:
        result = router_manager.list_routers()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/router/{router_name}")
async def disconnect_router(router_name: str):
    """
    Disconnect and remove router
    """
    try:
        result = router_manager.remove_router(router_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/router/command")
async def execute_router_command(request: RouterCommandRequest):
    """
    Execute single command on router
    """
    if not request.router_name or not request.command:
        raise HTTPException(status_code=400, detail="Router name and command are required")
    
    # Debug: print received command
    print(f"DEBUG: Received command: '{request.command}' (length: {len(request.command)})")
    print(f"DEBUG: Command bytes: {[ord(c) for c in request.command]}")
    
    try:
        result = router_manager.execute_command(request.router_name, request.command)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/router/config")
async def send_config_commands(request: RouterConfigRequest):
    """
    Send configuration commands to router
    """
    if not request.router_name or not request.commands:
        raise HTTPException(status_code=400, detail="Router name and commands are required")
    
    try:
        if request.router_name not in router_manager.connections:
            raise HTTPException(status_code=404, detail=f"Router {request.router_name} not found")
        
        router = router_manager.connections[request.router_name]
        result = router.send_config_commands(request.commands)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/router/{router_name}/info")
async def get_router_info(router_name: str):
    """
    Get router information (version, interfaces)
    """
    try:
        result = router_manager.get_router_info(router_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/router/{router_name}/backup")
async def backup_router_config(router_name: str):
    """
    Backup router configuration
    """
    try:
        result = router_manager.backup_config(router_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/router/{router_name}/logs")
async def get_router_logs(router_name: str, log_type: str = "all"):
    """
    Get router logs
    log_type: all, system, interface, routing
    """
    try:
        result = router_manager.get_logs(router_name, log_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== UTILITY ENDPOINTS ====================

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy", 
        "message": "Router Management Tools API is running",
        "connected_routers": len(router_manager.connections),
        "supported_vendors": list(router_manager.command_templates.keys())
    }

# ==================== VMANAGE ENDPOINTS ====================

@app.post("/api/vmanage/connect")
async def connect_vmanage(request: VManageConnectionRequest):
    """
    Connect to vManage controller
    """
    try:
        vmanage_client = VManageClient(
            host=request.host,
            username=request.username,
            password=request.password,
            port=request.port
        )
        
        auth_result = vmanage_client.authenticate()
        
        if auth_result["success"]:
            vmanage_clients[request.name] = vmanage_client
            return {
                "success": True,
                "message": f"Successfully connected to vManage {request.name}",
                "vmanage_host": request.host,
                "timestamp": auth_result["timestamp"]
            }
        else:
            return auth_result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/devices")
async def get_vmanage_devices(vmanage_name: str):
    """
    Get all devices from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_devices()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/edge-devices")
async def get_vmanage_edge_devices(vmanage_name: str):
    """
    Get edge devices specifically from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_edge_devices()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_id}")
async def get_vmanage_device_details(vmanage_name: str, device_id: str):
    """
    Get device details from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_device_details(device_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/templates")
async def get_vmanage_templates(vmanage_name: str):
    """
    Get all templates from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_templates()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/list")
async def list_vmanage_connections():
    """
    List all connected vManage instances
    """
    return {
        "success": True,
        "vmanage_connections": list(vmanage_clients.keys()),
        "count": len(vmanage_clients)
    }

@app.get("/api/vmanage/{vmanage_name}/tenants")
async def get_vmanage_tenants(vmanage_name: str):
    """
    Get all tenants from multitenant vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_tenants()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/tenant/switch")
async def switch_vmanage_tenant(vmanage_name: str, request: VManageTenantRequest):
    """
    Switch to specific tenant in multitenant vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        # Ambil tenant_id langsung; jika body bukan JSON valid, FastAPI akan 422 lebih awal
        tenant_id = request.tenant_id
        result = client.switch_tenant(tenant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/tenant/current")
async def get_current_tenant_info(vmanage_name: str):
    """
    Get current tenant information
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_current_tenant_info()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/tenant/refresh")
async def refresh_tenant_context(vmanage_name: str):
    """
    Refresh current tenant context to fix intermittent issues
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.refresh_tenant_context()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/vmanage/{vmanage_name}")
async def disconnect_vmanage(vmanage_name: str):
    """
    Disconnect from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not found")
    
    try:
        client = vmanage_clients[vmanage_name]
        client.close()
        del vmanage_clients[vmanage_name]
        
        return {
            "success": True,
            "message": f"Disconnected from vManage {vmanage_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# vManage CLI Tools Endpoints
@app.post("/api/vmanage/{vmanage_name}/tools/ping")
async def vmanage_ping(vmanage_name: str, request: VManagePingRequest):
    """
    Ping from vManage device to target IP
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.ping_device(request.device_ip, request.target_ip, request.vpn, request.count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/tools/traceroute")
async def vmanage_traceroute(vmanage_name: str, request: VManageTracerouteRequest):
    """
    Traceroute from vManage device to target IP
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.traceroute_device(request.device_ip, request.target_ip, request.vpn)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/tools/nslookup")
async def vmanage_nslookup(vmanage_name: str, request: VManageNslookupRequest):
    """
    NSLookup from vManage device
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.nslookup_device(request.device_ip, request.hostname, request.vpn, request.dns_server)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/stats/interface")
async def vmanage_interface_stats(vmanage_name: str, request: VManageInterfaceStatsRequest):
    """
    Retrieve interface statistics for a device from vManage
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")

    try:
        client = vmanage_clients[vmanage_name]
        print(f"[BACKEND] Interface stats request - device: {request.device_ip}, interface: {request.interface}, time_range: {request.time_range}, interval: {request.interval}")
        result = client.get_interface_statistics(request.device_ip, request.interface, request.time_range, request.interval)
        return result
    except Exception as e:
        print(f"[BACKEND] Interface stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/stats/tloc")
async def vmanage_tloc_stats(vmanage_name: str, request: VManageTlocStatsRequest):
    """
    Retrieve TLOC statistics from vManage with optional device and color filters
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")

    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_tloc_statistics(request.device_ip, request.color, request.time_range, request.interval)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_ip}/control-status")
async def vmanage_control_status(vmanage_name: str, device_ip: str):
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    try:
        client = vmanage_clients[vmanage_name]
        return client.get_control_status(device_ip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_ip}/counters")
async def vmanage_device_counters(vmanage_name: str, device_ip: str):
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    try:
        client = vmanage_clients[vmanage_name]
        return client.get_device_counters(device_ip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_ip}/system-status")
async def vmanage_system_status(vmanage_name: str, device_ip: str):
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    try:
        client = vmanage_clients[vmanage_name]
        return client.get_system_status(device_ip)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vmanage/{vmanage_name}/stats/approute/aggregation")
async def vmanage_approute_aggregation(vmanage_name: str, request: VManageApprouteAggRequest):
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    try:
        client = vmanage_clients[vmanage_name]
        return client.get_approute_aggregation(
            local_system_ip=request.local_system_ip,
            remote_system_ip=request.remote_system_ip,
            last_n_hours=request.last_n_hours,
            start_time_ms=request.start_time_ms,
            end_time_ms=request.end_time_ms,
            histogram_hours=request.histogram_hours,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_ip}/arp")
async def get_device_arp(vmanage_name: str, device_ip: str, vpn: str = "0"):
    """
    Get ARP table from device
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_device_arp(device_ip, vpn)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vmanage/{vmanage_name}/device/{device_ip}/interfaces")
async def get_device_interfaces(vmanage_name: str, device_ip: str):
    """
    Get interface status from device
    """
    if vmanage_name not in vmanage_clients:
        raise HTTPException(status_code=404, detail=f"vManage {vmanage_name} not connected")
    
    try:
        client = vmanage_clients[vmanage_name]
        result = client.get_device_interface_status(device_ip)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/supported-devices")
async def get_supported_devices():
    """
    Get list of supported router vendors
    """
    return {
        "supported_vendors": list(router_manager.command_templates.keys()),
        "commands": router_manager.command_templates
    }

# ==================== SSH WEB SOCKET CONSOLE ====================
@app.websocket("/ws/ssh/{router_name}")
async def websocket_ssh_console(websocket: WebSocket, router_name: str):
    """Bridge WebSocket <-> existing SSH interactive shell.
    Requires router already connected via REST. We don't close SSH on WS detach.
    """
    await websocket.accept()
    # --- Optional simple token auth ---
    required_token = os.environ.get("SSH_CONSOLE_TOKEN")
    if required_token:
        try:
            query_token = websocket.query_params.get("token")  # type: ignore
        except Exception:
            query_token = None
        if query_token != required_token:
            await websocket.send_text("[ERROR] Unauthorized (token)")
            await websocket.close()
            return
    if router_name not in router_manager.connections:
        await websocket.send_text(f"[ERROR] Router not connected: {router_name}\n")
        await websocket.close()
        return
    router = router_manager.connections[router_name]
    if not router.connected or not router.shell:
        await websocket.send_text("[ERROR] Router session inactive\n")
        await websocket.close()
        return
    shell = router.shell
    try:
        shell.settimeout(0.0)
    except Exception:
        pass

    stop_event = asyncio.Event()

    # --- Simple rate limiting (token bucket) per connection ---
    bucket_capacity = 4096  # max burst bytes from client
    refill_rate = 1024      # bytes per second
    available = bucket_capacity
    last_refill = time.time()

    def take_tokens(n):
        nonlocal available, last_refill
        now = time.time()
        elapsed = now - last_refill
        if elapsed > 0:
            available = min(bucket_capacity, available + elapsed * refill_rate)
            last_refill = now
        if n <= available:
            available -= n
            return True
        return False

    async def reader_loop():
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.06)
                try:
                    if shell.recv_ready():
                        chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                        if chunk:
                            await websocket.send_text(chunk.replace('\r\n', '\n'))
                except Exception:
                    await websocket.send_text("\n[ERROR] SSH read failure\n")
                    break
        except asyncio.CancelledError:
            pass

    reader_task = asyncio.create_task(reader_loop())
    await websocket.send_text(f"[INFO] Connected to SSH console for {router_name}. Type /exit to close.\n")
    try:
        while True:
            msg = await websocket.receive_text()
            if not take_tokens(len(msg)):
                await websocket.send_text("[WARN] Rate limit exceeded, input dropped\n")
                continue
            if msg.strip() in {"/exit", "exit"}:
                await websocket.send_text("[INFO] Detaching console...\n")
                break
            # Basic paste guard (avoid huge blobs)
            if len(msg) > 2000:
                await websocket.send_text("[WARN] Input too large, truncated.\n")
                msg = msg[:2000]
            # We send exactly what client sends; client will append \r for Enter.
            # This prevents accidental newline on every key.
            try:
                shell.send(msg)
            except Exception as e:
                await websocket.send_text(f"[ERROR] send failed: {e}\n")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"\n[ERROR] {e}\n")
        except Exception:
            pass
    finally:
        stop_event.set()
        await asyncio.sleep(0.1)
        if not reader_task.done():
            reader_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
        print(f"[WS] Console detached for {router_name}")

# ==================== BACKUP FILE MANAGEMENT ENDPOINTS ====================

@app.get("/api/backup/files")
async def list_backup_files():
    """List backup configuration files created by backup_config()
    Returns newest first with basic metadata."""
    try:
        logs_dir = (Path(__file__).resolve().parent / ".." / "logs").resolve()
        if not logs_dir.exists():
            return {"success": True, "files": [], "message": "Logs directory empty"}
        files = []
        for f in logs_dir.glob("*_config_*.txt"):
            try:
                stat = f.stat()
                files.append({
                    "filename": f.name,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "modified_iso": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except Exception:
                continue
        # Sort newest first
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "count": len(files), "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backup/download/{filename}")
async def download_backup_file(filename: str):
    """Download a specific backup file by filename.
    Security: only allow simple filenames containing '_config_' and ending .txt and located in logs dir."""
    if "/" in filename or ".." in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.endswith(".txt") or "_config_" not in filename:
        raise HTTPException(status_code=400, detail="Unsupported file pattern")
    logs_dir = (Path(__file__).resolve().parent / ".." / "logs").resolve()
    file_path = (logs_dir / filename).resolve()
    try:
        # Ensure still inside logs_dir
        if logs_dir not in file_path.parents and logs_dir != file_path.parent:
            raise HTTPException(status_code=400, detail="Path traversal detected")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(str(file_path), media_type="text/plain", filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004, reload=True)