version: '3.8'

services:
  otp-service:
    build: .
    container_name: otp-service
    ports:
      - "${PORT:-8000}:8000"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - JWT_ALGORITHM=${JWT_ALGORITHM:-HS256}
      - JWT_EXPIRATION_HOURS=${JWT_EXPIRATION_HOURS:-24}
      - API_KEY=${API_KEY}
      - RATE_LIMIT_REQUESTS=${RATE_LIMIT_REQUESTS:-100}
      - RATE_LIMIT_WINDOW=${RATE_LIMIT_WINDOW:-60}
      - DB_PATH=/data/otp_manager.db
      - UPLOAD_DIR=/data/uploads
      - HOST=0.0.0.0
      - PORT=8000
      - CORS_ORIGINS=${CORS_ORIGINS:-*}
      - DEBUG=${DEBUG:-false}
    volumes:
      - otp-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  otp-data:
    driver: local
