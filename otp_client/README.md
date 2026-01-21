# OTP Management Service

A production-ready REST API service for managing Time-Based One-Time Passwords (TOTP) with JWT authentication, rate limiting, and comprehensive security features.

## Features

- ✅ **JWT Authentication** - Secure token-based authentication
- ✅ **Rate Limiting** - Per-IP rate limiting to prevent abuse
- ✅ **QR Code Support** - Generate and import from QR codes
- ✅ **File Upload** - Upload QR code images to import secrets
- ✅ **RESTful API** - Clean, well-documented API endpoints
- ✅ **SQLite Database** - Lightweight, file-based storage
- ✅ **Docker Support** - Easy containerized deployment
- ✅ **Health Checks** - Built-in health monitoring
- ✅ **Comprehensive Logging** - Structured logging for monitoring
- ✅ **CORS Support** - Configurable cross-origin requests

## Quick Start

### Using Docker (Recommended)

1. **Create environment file:**
```bash
cp .env.example .env
# Edit .env and set your JWT_SECRET and API_KEY
```

2. **Generate secure secrets:**
```bash
# Generate JWT secret
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"

# Generate API key
python3 -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(32))"
```

3. **Start the service:**
```bash
docker-compose up -d
```

4. **Check health:**
```bash
curl http://localhost:8000/health
```

### Manual Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install system dependencies (for QR code scanning):**
```bash
# Ubuntu/Debian
sudo apt-get install libzbar0 libzbar-dev

# macOS
brew install zbar

# CentOS/RHEL
sudo yum install zbar
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run the service:**
```bash
python app.py
```

## API Documentation

### Authentication

All endpoints (except `/health` and `/api/v1/token`) require JWT authentication.

**Get Access Token:**
```bash
curl -X POST http://localhost:8000/api/v1/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Endpoints

#### 1. Create Client

Create a new OTP client with auto-generated secret:

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub"
  }'
```

Create with custom secret:
```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AWS",
    "secret": "JBSWY3DPEHPK3PXP"
  }'
```

Response:
```json
{
  "name": "GitHub",
  "secret": "JBSWY3DPEHPK3PXP",
  "created": "2024-01-20 10:30:00",
  "last_used": null,
  "qr_code_url": "/api/v1/clients/GitHub/qr"
}
```

#### 2. Import from QR Code

Import a client by uploading a QR code image:

```bash
curl -X POST "http://localhost:8000/api/v1/clients/import-qr?name=MyService" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "qr_file=@/path/to/qrcode.png"
```

#### 3. Generate OTP

Generate a one-time password for a client:

```bash
curl -X POST http://localhost:8000/api/v1/clients/GitHub/generate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "name": "GitHub",
  "otp": "123456",
  "expires_in": 27
}
```

#### 4. List All Clients

Get all registered clients:

```bash
curl http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
{
  "clients": [
    {
      "name": "GitHub",
      "secret": "JBSWY3DPEHPK3PXP",
      "created": "2024-01-20 10:30:00",
      "last_used": "2024-01-20 10:35:00",
      "qr_code_url": "/api/v1/clients/GitHub/qr"
    }
  ],
  "total": 1
}
```

#### 5. Get Client Details

Get detailed information about a specific client:

```bash
curl http://localhost:8000/api/v1/clients/GitHub \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### 6. Get QR Code

Download the QR code image for a client:

```bash
curl http://localhost:8000/api/v1/clients/GitHub/qr \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -o github_qr.png
```

#### 7. Delete Client

Delete a client:

```bash
curl -X DELETE http://localhost:8000/api/v1/clients/GitHub \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Health Check

Check service health:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00.000000",
  "database": "healthy"
}
```

## Configuration

All configuration is done through environment variables in the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key for JWT signing (REQUIRED) | - |
| `JWT_ALGORITHM` | JWT algorithm | HS256 |
| `JWT_EXPIRATION_HOURS` | Token expiration time | 24 |
| `API_KEY` | API key for token generation | - |
| `RATE_LIMIT_REQUESTS` | Max requests per time window | 100 |
| `RATE_LIMIT_WINDOW` | Rate limit window in seconds | 60 |
| `DB_PATH` | SQLite database file path | ~/.otp_manager_service.db |
| `UPLOAD_DIR` | Directory for QR code storage | /tmp/otp_uploads |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |
| `CORS_ORIGINS` | Allowed CORS origins | * |
| `DEBUG` | Enable debug mode | false |

## Security Features

### JWT Authentication
- Stateless authentication using JWT tokens
- Configurable expiration time
- Secure token validation on all protected endpoints

### Rate Limiting
- Per-IP rate limiting
- Configurable limits and time windows
- Automatic cleanup of old entries
- Thread-safe implementation

### Input Validation
- Client name validation (alphanumeric, spaces, hyphens, underscores)
- Secret format validation (base32)
- File type validation for uploads
- SQL injection prevention

### Database Security
- Parameterized queries prevent SQL injection
- Database file permissions set to 600 (owner read/write only)
- Automatic database initialization

### Error Handling
- Comprehensive error messages
- Separate error handling for development/production
- Structured logging for security events

## Development

### Running Tests

Create a test script:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Get token
response = requests.post(
    f"{BASE_URL}/api/v1/token",
    json={"api_key": "your-api-key"}
)
token = response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Create client
response = requests.post(
    f"{BASE_URL}/api/v1/clients",
    headers=headers,
    json={"name": "TestService"}
)
print("Created:", response.json())

# Generate OTP
response = requests.post(
    f"{BASE_URL}/api/v1/clients/TestService/generate",
    headers=headers
)
print("OTP:", response.json())
```

### Enable Debug Mode

Set in `.env`:
```
DEBUG=true
```

This enables:
- Auto-reload on code changes
- Verbose error messages in responses
- Detailed logging

## Production Deployment

### Using Docker

1. **Build and run:**
```bash
docker-compose up -d
```

2. **View logs:**
```bash
docker-compose logs -f
```

3. **Stop service:**
```bash
docker-compose down
```

### Using Systemd

Create `/etc/systemd/system/otp-service.service`:

```ini
[Unit]
Description=OTP Management Service
After=network.target

[Service]
Type=simple
User=otpuser
WorkingDirectory=/opt/otp-service
Environment="PATH=/opt/otp-service/venv/bin"
ExecStart=/opt/otp-service/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable otp-service
sudo systemctl start otp-service
sudo systemctl status otp-service
```

### Behind Nginx

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name otp.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring

### Health Checks

The service exposes a `/health` endpoint that returns:
- Overall service status
- Database connectivity
- Timestamp

Configure monitoring tools to check this endpoint regularly.

### Logging

Logs include:
- Authentication events
- Client operations (create, delete)
- OTP generation
- Rate limit violations
- Errors and exceptions

View logs:
```bash
# Docker
docker-compose logs -f

# Systemd
sudo journalctl -u otp-service -f
```

## API Client Examples

### Python

```python
import requests

class OTPClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.token = self._get_token(api_key)
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def _get_token(self, api_key):
        response = requests.post(
            f"{self.base_url}/api/v1/token",
            json={"api_key": api_key}
        )
        return response.json()["access_token"]
    
    def create_client(self, name, secret=None):
        data = {"name": name}
        if secret:
            data["secret"] = secret
        response = requests.post(
            f"{self.base_url}/api/v1/clients",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def generate_otp(self, name):
        response = requests.post(
            f"{self.base_url}/api/v1/clients/{name}/generate",
            headers=self.headers
        )
        return response.json()["otp"]

# Usage
client = OTPClient("http://localhost:8000", "your-api-key")
client.create_client("GitHub")
otp = client.generate_otp("GitHub")
print(f"OTP: {otp}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

class OTPClient {
    constructor(baseURL, apiKey) {
        this.baseURL = baseURL;
        this.apiKey = apiKey;
        this.token = null;
    }

    async authenticate() {
        const response = await axios.post(`${this.baseURL}/api/v1/token`, {
            api_key: this.apiKey
        });
        this.token = response.data.access_token;
    }

    async createClient(name, secret = null) {
        const data = { name };
        if (secret) data.secret = secret;
        
        const response = await axios.post(
            `${this.baseURL}/api/v1/clients`,
            data,
            { headers: { Authorization: `Bearer ${this.token}` } }
        );
        return response.data;
    }

    async generateOTP(name) {
        const response = await axios.post(
            `${this.baseURL}/api/v1/clients/${name}/generate`,
            {},
            { headers: { Authorization: `Bearer ${this.token}` } }
        );
        return response.data.otp;
    }
}

// Usage
(async () => {
    const client = new OTPClient('http://localhost:8000', 'your-api-key');
    await client.authenticate();
    await client.createClient('GitHub');
    const otp = await client.generateOTP('GitHub');
    console.log(`OTP: ${otp}`);
})();
```

### cURL Scripts

Save as `otp.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
API_KEY="your-api-key"

# Get token
TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/token" \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$API_KEY\"}" | jq -r '.access_token')

# Create client
create_client() {
    curl -s -X POST "$BASE_URL/api/v1/clients" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"name\": \"$1\"}" | jq
}

# Generate OTP
generate_otp() {
    curl -s -X POST "$BASE_URL/api/v1/clients/$1/generate" \
      -H "Authorization: Bearer $TOKEN" | jq -r '.otp'
}

# Usage
create_client "GitHub"
OTP=$(generate_otp "GitHub")
echo "OTP: $OTP"
```

## Troubleshooting

### Common Issues

**1. "JWT_SECRET must be set in .env file"**
- Create a `.env` file with a secure JWT_SECRET
- Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**2. "Could not extract secret from QR code"**
- Ensure QR code image is clear and readable
- QR code must contain a valid TOTP URI
- Check image file format (PNG, JPG supported)

**3. "Rate limit exceeded"**
- Wait for the rate limit window to reset
- Adjust RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW in .env

**4. "Database health check failed"**
- Check DB_PATH directory permissions
- Ensure sufficient disk space
- Verify SQLite is installed

**5. QR code scanning not working**
- Install libzbar: `sudo apt-get install libzbar0`
- Verify pyzbar installation: `pip install pyzbar`

## License

MIT License - feel free to use in your projects!
