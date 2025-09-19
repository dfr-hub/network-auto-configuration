from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network_tools import NetworkTools
from router_manager import RouterManager
from network_logger import NetworkLogger

app = FastAPI(title="Router Network Tools", version="1.0.0")

# Mount static files (frontend)
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Initialize tools
network_tools = NetworkTools()
router_manager = RouterManager()

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

class RouterCommandRequest(BaseModel):
    router_name: str
    command: str

class RouterConfigRequest(BaseModel):
    router_name: str
    commands: List[str]

# Root endpoint - serve frontend
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serve the main HTML page
    """
    try:
        with open("../frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
        <html>
            <head><title>Router Tools</title></head>
            <body>
                <h1>Router Network Tools</h1>
                <p>Frontend belum tersedia. Silakan akses API endpoints:</p>
                <ul>
                    <li><a href="/docs">/docs</a> - API Documentation</li>
                    <li>POST /api/ping - Ping tool</li>
                    <li>POST /api/traceroute - Traceroute tool</li>
                </ul>
            </body>
        </html>
        """)

# API Endpoints
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
        
        # Log hasil ke database
        log_id = network_logger.log_traceroute_result(result)
        result["log_id"] = log_id
        
        return result
    except Exception as e:
        # Log error juga
        error_result = {
            "success": False,
            "host": request.host,
            "error": str(e),
            "timestamp": network_tools._get_timestamp()
        }
        log_id = network_logger.log_traceroute_result(error_result)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "message": "Router Tools API is running"}

@app.get("/api/history/ping")
async def get_ping_history(host: Optional[str] = None, limit: int = 50):
    """
    Get ping history from database
    """
    try:
        history = network_logger.get_ping_history(host=host, limit=limit)
        return {
            "success": True,
            "count": len(history),
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/traceroute")
async def get_traceroute_history(host: Optional[str] = None, limit: int = 50):
    """
    Get traceroute history from database
    """
    try:
        history = network_logger.get_traceroute_history(host=host, limit=limit)
        return {
            "success": True,
            "count": len(history),
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics")
async def get_statistics():
    """
    Get network testing statistics
    """
    try:
        stats = network_logger.get_statistics()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)