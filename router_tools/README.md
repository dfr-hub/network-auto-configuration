# Network Auto Configuration

🚀 **Advanced Network Management Dashboard with Cisco SD-WAN vManage Integration**

A comprehensive web-based network management solution that provides real-time monitoring, automated configuration, and advanced analytics for Cisco SD-WAN infrastructure. Built with modern web technologies and robust backend APIs.

## 🌟 Features

### 📊 **Real-time Network Monitoring**
- **Interface Statistics**: Live throughput monitoring with Highcharts visualization
- **TLOC Statistics**: Network quality metrics (Loss%, Jitter, Latency)
- **Device Health Monitoring**: System status and performance metrics
- **Interactive Charts**: Professional data visualization with export capabilities

### 🔧 **Device Management**
- **Multi-vendor Support**: Cisco routers, switches, and SD-WAN devices
- **SSH Console Integration**: Direct terminal access with xterm.js
- **Automated Configuration**: Bulk device configuration and deployment
- **Device Discovery**: Automatic network topology mapping

### 🌐 **vManage Integration**
- **Cisco SD-WAN API**: Full integration with vManage REST APIs
- **Multi-tenant Support**: Seamless tenant switching and management
- **Authentication Management**: Secure session handling and CSRF protection
- **Real-time Data Sync**: Live statistics and monitoring data

### ⚡ **Modern Architecture**
- **FastAPI Backend**: High-performance Python REST API
- **Responsive Frontend**: Modern HTML5/CSS3/JavaScript dashboard
- **Real-time Updates**: WebSocket support for live data
- **Professional UI**: Clean, intuitive interface design

## 🛠️ Technology Stack

### Backend
- **Python 3.8+**: Core application logic
- **FastAPI**: Modern, fast web framework
- **Requests**: HTTP client for API integration
- **Paramiko**: SSH client for device management
- **Uvicorn**: ASGI web server

### Frontend
- **HTML5/CSS3**: Modern responsive design
- **JavaScript (ES6+)**: Interactive functionality
- **Highcharts**: Professional data visualization
- **Font Awesome**: Icon library
- **xterm.js**: Terminal emulation

### Integration
- **Cisco vManage API**: SD-WAN management
- **SSH/Telnet**: Direct device access
- **REST APIs**: Standardized communication

## 📋 Prerequisites

- Python 3.8 or higher
- Network access to managed devices
- Cisco vManage credentials (for SD-WAN features)
- Modern web browser (Chrome, Firefox, Edge)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/network-auto-configuration.git
cd network-auto-configuration
```

### 2. Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# For router-specific tools
pip install -r router_tools/requirements_router.txt
```

### 3. Configuration
```bash
# Copy example configuration
cp config.example.json config.json

# Edit configuration file
nano config.json
```

### 4. Run the Application
```bash
# Start the backend server
cd router_tools/backend
python main.py

# Server will start on http://localhost:8004
```

### 5. Access the Dashboard
Open your web browser and navigate to:
- **Main Dashboard**: `http://localhost:8004/modern_dashboard.html`
- **Router Management**: `http://localhost:8004/router_management.html`

## ⚙️ Configuration

### vManage API Configuration
Create `vmanageapi.json` in the `backend` directory:

```json
{
  "host": "your-vmanage-host.com",
  "username": "your-username",
  "password": "your-password",
  "tenant": "default",
  "port": 443,
  "verify_ssl": false,
  "timeout": 30
}
```

### Environment Variables
```bash
# Optional: Set environment variables
export VMANAGE_HOST=your-vmanage-host.com
export VMANAGE_USERNAME=your-username
export VMANAGE_PASSWORD=your-password
```

## 🏗️ Project Structure

```
network-auto-configuration/
├── 📁 router_tools/
│   ├── 📁 backend/
│   │   ├── 🐍 main.py                 # FastAPI application
│   │   ├── 🐍 main_router.py          # Main router entry point
│   │   ├── 🐍 vmanage_client.py       # vManage API client
│   │   ├── 🐍 router_manager.py       # Router management logic
│   │   ├── 🐍 network_tools.py        # Network utilities
│   │   ├── 🐍 ssh_helper.py           # SSH connection helper
│   │   ├── 🐍 port_scanner.py         # Port scanning tools
│   │   ├── 🐍 network_logger.py       # Logging utilities
│   │   └── 📄 vmanageapi.json         # vManage configuration
│   ├── 📁 frontend/
│   │   ├── 🌐 modern_dashboard.html   # Advanced monitoring dashboard
│   │   ├── 🌐 router_management.html  # Device management interface
│   │   └── 🌐 index.html              # Main web interface
│   ├── 📁 logs/                       # Application logs
│   ├── 📄 requirements.txt            # Python dependencies
│   └── 📄 requirements_router.txt     # Router-specific dependencies
├── 🐍 main_console.py                 # Console application entry
└── 📚 README.md                       # This documentation
```

## 🔌 API Documentation

### Network Monitoring Endpoints

#### Interface Statistics
```http
GET /api/interface-statistics/{device_uuid}?interval={interval}
```
**Parameters:**
- `device_uuid`: Device identifier in vManage
- `interval`: Time interval (5min, 1hr, 1day)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "timestamp": 1634567890000,
      "interface": "GigabitEthernet0/0/0",
      "tx_octets": 1234567890,
      "rx_octets": 987654321,
      "tx_packets": 12345,
      "rx_packets": 9876
    }
  ]
}
```

#### TLOC Statistics
```http
GET /api/tloc-statistics/{device_uuid}?interval={interval}
```

#### Device Management
```http
GET /api/devices
POST /api/devices/{device_id}/command
PUT /api/devices/{device_id}/config
```

### Network Tools

#### Ping Test
```http
POST /api/ping
Content-Type: application/json

{
  "host": "192.168.1.1",
  "count": 4,
  "timeout": 3
}
```

#### Port Scanning
```http
POST /api/port-scan
Content-Type: application/json

{
  "target": "192.168.1.1",
  "ports": [22, 23, 80, 443, 8080],
  "timeout": 5
}
```

#### SSH Command Execution
```http
POST /api/ssh/execute
Content-Type: application/json

{
  "host": "192.168.1.1",
  "username": "admin",
  "password": "password",
  "command": "show version"
}
```

### Health Check
```http
GET /api/health
```

## 📱 Usage Examples

### 1. Modern Dashboard
Access the main monitoring interface at `http://localhost:8004/modern_dashboard.html`

**Features:**
- **Real-time Interface Statistics**: Monitor bandwidth utilization with interactive Highcharts
- **TLOC Performance**: Track tunnel performance metrics
- **Time Range Selection**: 5 minutes, 1 hour, 1 day intervals
- **Device Selection**: Filter by specific network devices
- **Export Functionality**: Download charts as PNG/PDF

### 2. Router Management Interface
Navigate to `http://localhost:8004/router_management.html`

**Capabilities:**
- **Device Discovery**: Automatic network device detection
- **SSH Terminal**: Direct command-line access to devices
- **Configuration Management**: Backup and restore device configs
- **Bulk Operations**: Execute commands across multiple devices

### 3. API Integration Examples

#### Python Integration
```python
import requests
import json

# Initialize API client
BASE_URL = "http://localhost:8004"

# Get interface statistics
def get_interface_stats(device_uuid, interval="5min"):
    url = f"{BASE_URL}/api/interface-statistics/{device_uuid}"
    params = {"interval": interval}
    response = requests.get(url, params=params)
    return response.json()

# Execute device command via SSH
def execute_ssh_command(host, username, password, command):
    url = f"{BASE_URL}/api/ssh/execute"
    payload = {
        "host": host,
        "username": username,
        "password": password,
        "command": command
    }
    response = requests.post(url, json=payload)
    return response.json()

# Usage examples
stats = get_interface_stats("device-uuid-123", "1hr")
result = execute_ssh_command("192.168.1.1", "admin", "password", "show ip route")
```

#### JavaScript Integration
```javascript
// Fetch interface statistics
async function fetchInterfaceStats(deviceUuid, interval = '5min') {
    try {
        const response = await fetch(
            `/api/interface-statistics/${deviceUuid}?interval=${interval}`
        );
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

// Update dashboard charts
async function updateDashboard() {
    const stats = await fetchInterfaceStats('device-123', '1hr');
    if (stats && stats.success) {
        updateHighcharts(stats.data);
    }
}
```

## 🔧 Advanced Configuration

### Environment Variables
```bash
# vManage API Configuration
export VMANAGE_HOST=your-vmanage-server.com
export VMANAGE_USERNAME=your-username
export VMANAGE_PASSWORD=your-password
export VMANAGE_TENANT=default

# Application Settings
export DEBUG=true
export LOG_LEVEL=INFO
export API_PORT=8004

# Security Settings  
export JWT_SECRET_KEY=your-secret-key
export ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
```

### Custom Configuration File
Create `config.json` in the root directory:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8004,
    "debug": false,
    "log_level": "INFO"
  },
  "vmanage": {
    "host": "your-vmanage-server.com",
    "port": 443,
    "verify_ssl": false,
    "timeout": 30,
    "retry_attempts": 3
  },
  "monitoring": {
    "default_interval": "5min",
    "max_data_points": 1000,
    "cache_timeout": 300
  },
  "ssh": {
    "default_timeout": 10,
    "connection_retries": 3,
    "keepalive_interval": 60
  }
}
```

## 🚀 Deployment

### Production Deployment
```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:8004

# Or using Docker
docker build -t network-auto-config .
docker run -p 8004:8004 network-auto-config
```

### Docker Configuration
Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8004

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8004"]
```

## Response Format

### Ping Response
```json
{
  "success": true,
  "host": "google.com",
  "packets_sent": 4,
  "packets_received": 4, 
  "packet_loss": 0,
  "packet_loss_percent": 0.0,
  "min_time_ms": 10,
  "max_time_ms": 15,
  "avg_time_ms": 12,
  "replies": [10, 12, 11, 15],
  "raw_output": "...",
  "timestamp": "2025-09-16T10:30:00"
}
```

### Traceroute Response
```json
{
  "success": true,
  "host": "google.com",
  "total_hops": 8,
  "hops": [
    {
      "hop": 1,
      "hostname": "192.168.1.1", 
      "times": ["1 ms", "1 ms", "2 ms"],
      "raw_line": "1    1 ms    1 ms    2 ms  192.168.1.1"
    }
  ],
  "raw_output": "...",
  "timestamp": "2025-09-16T10:30:00"
}
```

## 🛠️ Troubleshooting

### Common Issues

#### vManage API Connection
```bash
# Test API connectivity
curl -k https://your-vmanage-host.com/dataservice/device

# Check SSL certificate issues
openssl s_client -connect your-vmanage-host.com:443
```

#### Port Conflicts
```bash
# Windows: Check port usage
netstat -ano | findstr :8004

# Linux/Mac: Check port usage  
lsof -i :8004

# Kill conflicting process
taskkill /PID <process_id> /F  # Windows
kill -9 <process_id>           # Linux/Mac
```

#### Python Environment Issues
```bash
# Verify Python version
python --version

# Check installed packages
pip list

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### Debug Mode
Enable debug logging by setting environment variable:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the Repository**
   ```bash
   git clone https://github.com/yourusername/network-auto-configuration.git
   cd network-auto-configuration
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make Your Changes**
   - Add new features or fix bugs
   - Follow PEP 8 coding standards
   - Add appropriate tests
   - Update documentation

4. **Commit and Push**
   ```bash
   git commit -m "Add amazing feature"
   git push origin feature/amazing-feature
   ```

5. **Create Pull Request**
   - Provide clear description
   - Reference any related issues
   - Include screenshots if applicable

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Code formatting
black backend/ frontend/
flake8 backend/

# Type checking
mypy backend/
```

### API Documentation
- **Swagger UI**: `http://localhost:8004/docs`
- **ReDoc**: `http://localhost:8004/redoc`

## 📊 Performance Monitoring

### Metrics Collection
The application provides built-in performance monitoring:

- **API Response Times**: Track endpoint performance
- **vManage Query Duration**: Monitor SD-WAN API calls
- **Memory Usage**: Track application resource consumption
- **Error Rates**: Monitor system health

### Health Check Endpoint
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "uptime": 3600,
  "memory_usage": "45.2 MB",
  "active_connections": 12,
  "vmanage_status": "connected"
}
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Authors & Contributors

- **Lead Developer**: Network Automation Team
- **Contributors**: Community developers and network engineers

## 📞 Support & Contact

- **Documentation**: [GitHub Wiki](https://github.com/yourusername/network-auto-configuration/wiki)
- **Issues**: [GitHub Issues](https://github.com/yourusername/network-auto-configuration/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/network-auto-configuration/discussions)

## 🔄 Changelog

### v2.0.0 (Current)
- ✅ **vManage Integration**: Complete Cisco SD-WAN support
- ✅ **Advanced Dashboards**: Real-time monitoring with Highcharts
- ✅ **Interface Statistics**: Bandwidth and performance monitoring
- ✅ **TLOC Analytics**: Tunnel performance tracking
- ✅ **Multi-Interval Support**: 5min, 1hr, 1day time ranges
- ✅ **Professional UI**: Modern responsive design
- ✅ **Export Functionality**: Chart export to PNG/PDF

### v1.0.0 (Previous)
- ✅ Basic network tools (ping, traceroute, port scan)
- ✅ SSH device management
- ✅ Web interface
- ✅ RESTful API

### 🚀 Roadmap
- 🔄 **AI-Powered Analytics**: Machine learning for network insights  
- 🔄 **Multi-Vendor Support**: Extend beyond Cisco devices
- 🔄 **Automated Remediation**: Self-healing network capabilities
- 🔄 **Mobile App**: iOS/Android companion applications
- 🔄 **Advanced Alerting**: Intelligent notification system

---

<div align="center">

**Network Auto Configuration** - Empowering Network Engineers with Intelligent Automation

[![GitHub Stars](https://img.shields.io/github/stars/yourusername/network-auto-configuration?style=social)](https://github.com/yourusername/network-auto-configuration)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://python.org)

</div>