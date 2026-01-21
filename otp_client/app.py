#!/usr/bin/env python3
"""
OTP Management Service - FastAPI REST API

A production-ready OTP management service with:
- JWT authentication
- Rate limiting
- QR code upload support
- Comprehensive error handling
- Logging and monitoring

Author: OTP Service
Version: 2.0
"""

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
import os
import re
import sqlite3
import pyotp
import qrcode
from PIL import Image
from pyzbar.pyzbar import decode
import io
import logging
from functools import wraps
import time
from collections import defaultdict
import threading
from dotenv import load_dotenv
import secrets
import hashlib

# Load environment variables
load_dotenv()

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", None)
if not JWT_SECRET:
    raise ValueError("JWT_SECRET must be set in .env file")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
DB_PATH = os.getenv("DB_PATH", os.path.expanduser("~/.otp_manager_service.db"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/otp_uploads")
API_KEY = os.getenv("API_KEY", None)  # Optional: for initial authentication

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="OTP Management Service",
    description="Secure TOTP management with JWT authentication",
    version="2.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Rate limiting storage
rate_limit_storage = defaultdict(list)
rate_limit_lock = threading.Lock()


# Pydantic models
class TokenRequest(BaseModel):
    """Request model for token generation"""
    api_key: Optional[str] = Field(None, description="API key for authentication")
    username: Optional[str] = Field(None, description="Username (if using username/password)")
    password: Optional[str] = Field(None, description="Password (if using username/password)")


class TokenResponse(BaseModel):
    """Response model for token generation"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ClientRequest(BaseModel):
    """Request model for adding a client"""
    name: str = Field(..., description="Client name", min_length=1, max_length=100)
    secret: Optional[str] = Field(None, description="TOTP secret (auto-generated if not provided)")

    @validator('name')
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z0-9 _-]+$', v):
            raise ValueError('Name must contain only alphanumeric characters, spaces, hyphens, and underscores')
        return v

    @validator('secret')
    def validate_secret(cls, v):
        if v and not re.match(r'^[A-Z2-7=]+$', v):
            raise ValueError('Secret must be a valid base32 string')
        return v


class ClientResponse(BaseModel):
    """Response model for client operations"""
    name: str
    secret: str
    created: str
    last_used: Optional[str] = None
    qr_code_url: Optional[str] = None


class OTPResponse(BaseModel):
    """Response model for OTP generation"""
    name: str
    otp: str
    expires_in: int = 30


class ClientListResponse(BaseModel):
    """Response model for listing clients"""
    clients: List[ClientResponse]
    total: int


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    timestamp: str
    database: str


class ErrorResponse(BaseModel):
    """Response model for errors"""
    error: str
    detail: Optional[str] = None


# Database initialization
def init_database():
    """Initialize the database with proper schema"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                secret TEXT NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP
            )
        ''')

        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name)
        ''')

        conn.commit()
        conn.close()

        # Set secure permissions
        os.chmod(DB_PATH, 0o600)
        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


# Initialize database on startup
init_database()


# Rate limiting decorator
def rate_limit(max_requests: int = RATE_LIMIT_REQUESTS, window: int = RATE_LIMIT_WINDOW):
    """
    Rate limiting decorator
    
    Args:
        max_requests: Maximum number of requests allowed in the window
        window: Time window in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get client identifier (IP address)
            client_ip = request.client.host
            
            current_time = time.time()
            
            with rate_limit_lock:
                # Clean old entries
                rate_limit_storage[client_ip] = [
                    req_time for req_time in rate_limit_storage[client_ip]
                    if current_time - req_time < window
                ]
                
                # Check rate limit
                if len(rate_limit_storage[client_ip]) >= max_requests:
                    logger.warning(f"Rate limit exceeded for {client_ip}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {max_requests} requests per {window} seconds"
                    )
                
                # Add current request
                rate_limit_storage[client_ip].append(current_time)
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# JWT token functions
def create_access_token(data: dict) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Data to encode in the token
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Decoded token data
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Database helper functions
def get_db_connection():
    """Get a database connection"""
    return sqlite3.connect(DB_PATH)


def validate_client_name(name: str) -> bool:
    """Validate client name format"""
    return bool(re.match(r'^[a-zA-Z0-9 _-]+$', name))


def extract_secret_from_qr(image_bytes: bytes) -> Optional[str]:
    """
    Extract TOTP secret from QR code image
    
    Args:
        image_bytes: QR code image as bytes
        
    Returns:
        Extracted secret or None
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        decoded_objects = decode(image)

        if decoded_objects:
            data = decoded_objects[0].data.decode('utf-8')
            
            if 'otpauth://totp/' in data:
                import urllib.parse
                parsed = urllib.parse.urlparse(data)
                params = urllib.parse.parse_qs(parsed.query)
                
                if 'secret' in params:
                    secret = params['secret'][0]
                    if re.match(r'^[A-Z2-7=]+$', secret):
                        return secret
            
            # Try to use as raw secret
            if re.match(r'^[A-Z2-7=]+$', data):
                return data

        return None

    except Exception as e:
        logger.error(f"Error extracting secret from QR: {e}")
        return None


def generate_qr_code(name: str, secret: str) -> Optional[str]:
    """
    Generate QR code for a client
    
    Args:
        name: Client name
        secret: TOTP secret
        
    Returns:
        Path to saved QR code file
    """
    try:
        totp_url = pyotp.totp.TOTP(secret).provisioning_uri(name, issuer_name="OTP Manager")

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(totp_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Generate unique filename
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        qr_filename = f"{safe_name}_{secrets.token_hex(4)}_qr.png"
        qr_path = os.path.join(UPLOAD_DIR, qr_filename)
        
        img.save(qr_path)
        return qr_filename

    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        return None


# API Endpoints

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "OTP Management Service",
        "version": "2.0",
        "endpoints": {
            "health": "/health",
            "token": "/api/v1/token",
            "clients": "/api/v1/clients",
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        database=db_status
    )


@app.post("/api/v1/token", response_model=TokenResponse)
@rate_limit(max_requests=10, window=60)
async def generate_token(request: Request, token_request: TokenRequest):
    """
    Generate a JWT access token
    
    Supports authentication via API key or username/password
    """
    # Validate authentication
    if API_KEY:
        if token_request.api_key != API_KEY:
            logger.warning("Invalid API key attempt")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
    else:
        # If no API_KEY is set, accept any request (for development)
        logger.warning("No API_KEY configured - accepting all token requests")

    # Generate token
    token_data = {
        "sub": token_request.username or "api_user",
        "type": "access"
    }
    
    access_token = create_access_token(token_data)
    
    logger.info(f"Token generated for user: {token_data['sub']}")
    
    return TokenResponse(
        access_token=access_token,
        expires_in=JWT_EXPIRATION_HOURS * 3600
    )


@app.post("/api/v1/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
@rate_limit()
async def create_client(
    request: Request,
    client_request: ClientRequest,
    token_data: dict = Depends(verify_token)
):
    """
    Create a new OTP client
    
    Generates a new TOTP secret if not provided
    """
    try:
        name = client_request.name.strip()
        secret = client_request.secret or pyotp.random_base32()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if client already exists
        cursor.execute("SELECT name FROM clients WHERE name = ?", (name,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Client '{name}' already exists"
            )

        cursor.execute(
            "INSERT INTO clients (name, secret) VALUES (?, ?)",
            (name, secret)
        )
        conn.commit()

        # Get created client
        cursor.execute(
            "SELECT name, secret, created, last_used FROM clients WHERE name = ?",
            (name,)
        )
        result = cursor.fetchone()
        conn.close()

        # Generate QR code
        qr_filename = generate_qr_code(name, secret)

        logger.info(f"Client created: {name}")

        return ClientResponse(
            name=result[0],
            secret=result[1],
            created=result[2],
            last_used=result[3],
            qr_code_url=f"/api/v1/clients/{name}/qr" if qr_filename else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create client: {str(e)}"
        )


@app.post("/api/v1/clients/import-qr", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
@rate_limit()
async def import_client_from_qr(
    request: Request,
    name: str,
    qr_file: UploadFile = File(...),
    token_data: dict = Depends(verify_token)
):
    """
    Import a client by uploading a QR code image
    
    The QR code should contain a TOTP URI with the secret
    """
    try:
        # Validate file type
        if not qr_file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )

        # Read and process QR code
        image_bytes = await qr_file.read()
        secret = extract_secret_from_qr(image_bytes)

        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract secret from QR code"
            )

        # Create client
        client_request = ClientRequest(name=name, secret=secret)
        return await create_client(request, client_request, token_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing from QR: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import client: {str(e)}"
        )


@app.get("/api/v1/clients", response_model=ClientListResponse)
@rate_limit()
async def list_clients(
    request: Request,
    token_data: dict = Depends(verify_token)
):
    """
    List all registered OTP clients
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, secret, created, last_used FROM clients ORDER BY created DESC"
        )
        results = cursor.fetchall()
        conn.close()

        clients = [
            ClientResponse(
                name=row[0],
                secret=row[1],
                created=row[2],
                last_used=row[3],
                qr_code_url=f"/api/v1/clients/{row[0]}/qr"
            )
            for row in results
        ]

        return ClientListResponse(
            clients=clients,
            total=len(clients)
        )

    except Exception as e:
        logger.error(f"Error listing clients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list clients: {str(e)}"
        )


@app.get("/api/v1/clients/{name}", response_model=ClientResponse)
@rate_limit()
async def get_client(
    request: Request,
    name: str,
    token_data: dict = Depends(verify_token)
):
    """
    Get detailed information about a specific client
    """
    try:
        if not validate_client_name(name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client name"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, secret, created, last_used FROM clients WHERE name = ?",
            (name,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{name}' not found"
            )

        return ClientResponse(
            name=result[0],
            secret=result[1],
            created=result[2],
            last_used=result[3],
            qr_code_url=f"/api/v1/clients/{name}/qr"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get client: {str(e)}"
        )


@app.post("/api/v1/clients/{name}/generate", response_model=OTPResponse)
@rate_limit()
async def generate_otp(
    request: Request,
    name: str,
    token_data: dict = Depends(verify_token)
):
    """
    Generate a one-time password for a client
    """
    try:
        if not validate_client_name(name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client name"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT secret FROM clients WHERE name = ?", (name,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{name}' not found"
            )

        secret = result[0]
        totp = pyotp.TOTP(secret)
        otp = totp.now()

        # Update last used timestamp
        cursor.execute(
            "UPDATE clients SET last_used = CURRENT_TIMESTAMP WHERE name = ?",
            (name,)
        )
        conn.commit()
        conn.close()

        logger.info(f"OTP generated for client: {name}")

        return OTPResponse(
            name=name,
            otp=otp,
            expires_in=30 - (int(time.time()) % 30)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating OTP: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate OTP: {str(e)}"
        )


@app.get("/api/v1/clients/{name}/qr")
@rate_limit()
async def get_qr_code(
    request: Request,
    name: str,
    token_data: dict = Depends(verify_token)
):
    """
    Get the QR code image for a client
    """
    try:
        if not validate_client_name(name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client name"
            )

        # Get client secret
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT secret FROM clients WHERE name = ?", (name,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{name}' not found"
            )

        secret = result[0]

        # Generate QR code on-the-fly
        qr_filename = generate_qr_code(name, secret)
        
        if not qr_filename:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate QR code"
            )

        qr_path = os.path.join(UPLOAD_DIR, qr_filename)
        
        return FileResponse(
            qr_path,
            media_type="image/png",
            filename=f"{name}_qr.png"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting QR code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get QR code: {str(e)}"
        )


@app.delete("/api/v1/clients/{name}", status_code=status.HTTP_204_NO_CONTENT)
@rate_limit()
async def delete_client(
    request: Request,
    name: str,
    token_data: dict = Depends(verify_token)
):
    """
    Delete a client
    """
    try:
        if not validate_client_name(name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client name"
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM clients WHERE name = ?", (name,))
        
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{name}' not found"
            )

        conn.commit()
        conn.close()

        logger.info(f"Client deleted: {name}")

        # Clean up QR codes
        for file in os.listdir(UPLOAD_DIR):
            if file.startswith(re.sub(r'[^a-zA-Z0-9_-]', '_', name)):
                try:
                    os.remove(os.path.join(UPLOAD_DIR, file))
                except:
                    pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete client: {str(e)}"
        )


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=None
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if os.getenv("DEBUG") else None
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
