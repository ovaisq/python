# OTP Service Deployment Guide

This guide covers deploying the OTP Management Service in various environments.

## Table of Contents

1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Production Deployment (Ubuntu/Debian)](#production-deployment)
4. [Production Deployment (RHEL/CentOS)](#production-deployment-rhelcentos)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Security Hardening](#security-hardening)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Backup and Recovery](#backup-and-recovery)

---

## Local Development

### Quick Start

```bash
# Run the setup script
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Start the service
python app.py
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libzbar0 libzbar-dev

# Create .env file
cp .env.example .env
# Edit .env and set JWT_SECRET and API_KEY

# Run the service
python app.py
```

---

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Create .env file
cp .env.example .env
# Edit .env with your settings

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Using Docker Directly

```bash
# Build image
docker build -t otp-service:latest .

# Run container
docker run -d \
  --name otp-service \
  -p 8000:8000 \
  -v otp-data:/data \
  -e JWT_SECRET="your-secret-here" \
  -e API_KEY="your-api-key-here" \
  otp-service:latest

# View logs
docker logs -f otp-service
```

---

## Production Deployment

### Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Python 3.8+
- Nginx (for reverse proxy)
- SSL certificate (Let's Encrypt recommended)

### Step 1: System Setup

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y python3 python3-pip python3-venv \
  libzbar0 libzbar-dev nginx certbot python3-certbot-nginx

# Create service user
sudo useradd -r -s /bin/false -d /opt/otp-service otpuser

# Create directories
sudo mkdir -p /opt/otp-service
sudo mkdir -p /var/lib/otp-service/uploads
sudo chown -R otpuser:otpuser /opt/otp-service /var/lib/otp-service
```

### Step 2: Application Setup

```bash
# Copy application files
sudo cp -r /path/to/otp_service/* /opt/otp-service/
sudo chown -R otpuser:otpuser /opt/otp-service

# Switch to service user
sudo -u otpuser -s

# Create virtual environment
cd /opt/otp-service
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
DB_PATH=/var/lib/otp-service/otp_manager.db
UPLOAD_DIR=/var/lib/otp-service/uploads
HOST=127.0.0.1
PORT=8000
DEBUG=false
EOF

# Exit service user
exit
```

### Step 3: Systemd Service

```bash
# Copy systemd service file
sudo cp /opt/otp-service/otp-service.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable otp-service
sudo systemctl start otp-service

# Check status
sudo systemctl status otp-service
```

### Step 4: Nginx Configuration

```bash
# Copy nginx configuration
sudo cp /opt/otp-service/nginx.conf /etc/nginx/sites-available/otp-service

# Edit configuration
sudo nano /etc/nginx/sites-available/otp-service
# Update server_name to your domain

# Enable site
sudo ln -s /etc/nginx/sites-available/otp-service /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Step 5: SSL Certificate

```bash
# Get SSL certificate with Let's Encrypt
sudo certbot --nginx -d otp.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

### Step 6: Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

---

## Production Deployment (RHEL/CentOS)

```bash
# Install dependencies
sudo yum install -y python3 python3-pip python3-virtualenv \
  zbar nginx certbot python3-certbot-nginx

# Follow similar steps as Ubuntu deployment
# Use firewalld instead of ufw:
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## Kubernetes Deployment

### Create Kubernetes manifests

**namespace.yaml**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: otp-service
```

**secret.yaml**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: otp-service-secrets
  namespace: otp-service
type: Opaque
stringData:
  JWT_SECRET: "your-jwt-secret-here"
  API_KEY: "your-api-key-here"
```

**configmap.yaml**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otp-service-config
  namespace: otp-service
data:
  JWT_ALGORITHM: "HS256"
  JWT_EXPIRATION_HOURS: "24"
  RATE_LIMIT_REQUESTS: "100"
  RATE_LIMIT_WINDOW: "60"
  DB_PATH: "/data/otp_manager.db"
  UPLOAD_DIR: "/data/uploads"
  HOST: "0.0.0.0"
  PORT: "8000"
  CORS_ORIGINS: "*"
  DEBUG: "false"
```

**deployment.yaml**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otp-service
  namespace: otp-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: otp-service
  template:
    metadata:
      labels:
        app: otp-service
    spec:
      containers:
      - name: otp-service
        image: otp-service:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: otp-service-config
        - secretRef:
            name: otp-service-secrets
        volumeMounts:
        - name: data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: otp-service-pvc
```

**service.yaml**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: otp-service
  namespace: otp-service
spec:
  selector:
    app: otp-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

**pvc.yaml**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: otp-service-pvc
  namespace: otp-service
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

Deploy:
```bash
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f pvc.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

---

## Security Hardening

### 1. Strong Secrets

```bash
# Generate strong JWT secret (32 bytes)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate strong API key (32 bytes)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. File Permissions

```bash
# Secure .env file
chmod 600 /opt/otp-service/.env
chown otpuser:otpuser /opt/otp-service/.env

# Secure database
chmod 600 /var/lib/otp-service/otp_manager.db
chown otpuser:otpuser /var/lib/otp-service/otp_manager.db
```

### 3. Rate Limiting

Configure aggressive rate limits in `.env`:
```
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60
```

### 4. Network Security

```bash
# Restrict service to localhost (let nginx handle external access)
HOST=127.0.0.1
```

### 5. SELinux (RHEL/CentOS)

```bash
# Set proper SELinux contexts
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/otp-service(/.*)?"
sudo restorecon -Rv /opt/otp-service
```

---

## Monitoring and Logging

### Systemd Logs

```bash
# View service logs
sudo journalctl -u otp-service -f

# View logs since boot
sudo journalctl -u otp-service -b

# Export logs
sudo journalctl -u otp-service > otp-service.log
```

### Application Logs

The service logs to stdout/stderr which systemd captures. For file-based logging, modify `app.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/otp-service/app.log'),
        logging.StreamHandler()
    ]
)
```

### Monitoring with Prometheus

Add metrics endpoint to `app.py`:

```python
from prometheus_client import Counter, Histogram, generate_latest

otp_requests = Counter('otp_requests_total', 'Total OTP requests')
otp_latency = Histogram('otp_request_duration_seconds', 'Request latency')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

---

## Backup and Recovery

### Database Backup

```bash
# Create backup script
cat > /opt/otp-service/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/otp-service"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
sqlite3 /var/lib/otp-service/otp_manager.db ".backup $BACKUP_DIR/otp_manager_$DATE.db"

# Backup .env
cp /opt/otp-service/.env $BACKUP_DIR/env_$DATE

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "env_*" -mtime +30 -delete
EOF

chmod +x /opt/otp-service/backup.sh
```

### Automated Backups

```bash
# Add to crontab
sudo crontab -e

# Add line (backup daily at 2 AM)
0 2 * * * /opt/otp-service/backup.sh
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop otp-service

# Restore database
cp /var/backups/otp-service/otp_manager_YYYYMMDD_HHMMSS.db \
   /var/lib/otp-service/otp_manager.db

# Set permissions
sudo chown otpuser:otpuser /var/lib/otp-service/otp_manager.db
sudo chmod 600 /var/lib/otp-service/otp_manager.db

# Start service
sudo systemctl start otp-service
```

---

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u otp-service -n 50

# Check permissions
ls -la /opt/otp-service
ls -la /var/lib/otp-service

# Test manually
sudo -u otpuser /opt/otp-service/venv/bin/python /opt/otp-service/app.py
```

### High CPU usage

```bash
# Check for rate limit abuse
grep "Rate limit" /var/log/nginx/otp-service-access.log

# Monitor connections
netstat -an | grep :8000 | wc -l
```

### Database locked errors

```bash
# Check for multiple instances
ps aux | grep app.py

# Check file permissions
ls -la /var/lib/otp-service/otp_manager.db
```

---

## Performance Tuning

### Nginx

```nginx
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
```

### Systemd

```ini
[Service]
LimitNOFILE=65536
LimitNPROC=4096
```

### Database

```bash
# Regular vacuum
sqlite3 /var/lib/otp-service/otp_manager.db "VACUUM;"

# Add to cron
0 3 * * 0 sqlite3 /var/lib/otp-service/otp_manager.db "VACUUM;"
```

---

## Health Checks

### Script

```bash
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s $HEALTH_URL)

if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
    echo "Service is healthy"
    exit 0
else
    echo "Service is unhealthy: $RESPONSE"
    exit 1
fi
```

### Uptime Monitor

Configure with services like:
- UptimeRobot
- Pingdom
- StatusCake

Monitor: `https://otp.yourdomain.com/health`
