#!/bin/bash
set -e

echo "=================================="
echo "OTP Service Quick Start Setup"
echo "=================================="
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists"
    read -p "Do you want to overwrite it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Using existing .env file"
        ENV_EXISTS=true
    fi
fi

if [ -z "$ENV_EXISTS" ]; then
    echo "Creating .env file..."
    
    # Generate secure secrets
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Create .env file
    cat > .env << EOF
# JWT Configuration
JWT_SECRET=$JWT_SECRET
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API Key for token generation
API_KEY=$API_KEY

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Database
DB_PATH=/var/lib/otp_service/otp_manager.db

# Upload Directory
UPLOAD_DIR=/var/lib/otp_service/uploads

# Server Configuration
HOST=0.0.0.0
PORT=8000

# CORS Configuration
CORS_ORIGINS=*

# Debug Mode
DEBUG=false
EOF
    
    echo "✓ .env file created with secure random secrets"
    echo ""
    echo "Your API Key: $API_KEY"
    echo "Save this key - you'll need it to generate tokens!"
    echo ""
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Create data directories
echo "Creating data directories..."
mkdir -p /tmp/otp_uploads
echo "✓ Data directories created"

# Check for system dependencies
echo ""
echo "Checking system dependencies..."

if ! dpkg -l | grep -q libzbar0; then
    echo "libzbar0 not found (needed for QR code scanning)"
    echo "Install with: sudo apt-get install libzbar0"
else
    echo "✓ libzbar0 found"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To start the service:"
echo "  source venv/bin/activate"
echo "  python3 app.py"
echo ""
echo "Or use Docker:"
echo "  docker-compose up -d"
echo ""
echo "Or use make commands:"
echo "  make run"
echo ""
echo "Your API Key: $(grep API_KEY .env | cut -d '=' -f2)"
echo ""
echo "Get a token:"
echo "  curl -X POST http://localhost:8000/api/v1/token \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"api_key\": \"$(grep API_KEY .env | cut -d '=' -f2)\"}'"
echo ""
echo "Run tests:"
echo "  python3 test_api.py --api-key $(grep API_KEY .env | cut -d '=' -f2)"
echo ""
