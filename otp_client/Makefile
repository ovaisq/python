.PHONY: help install run test docker-build docker-run docker-stop clean

help:
	@echo "OTP Service - Available Commands"
	@echo "================================="
	@echo "make install       - Install dependencies"
	@echo "make run           - Run the service locally"
	@echo "make test          - Run API tests"
	@echo "make docker-build  - Build Docker image"
	@echo "make docker-run    - Run with Docker Compose"
	@echo "make docker-stop   - Stop Docker containers"
	@echo "make clean         - Clean temporary files"
	@echo "make setup         - Initial setup (create .env)"

setup:
	@echo "Setting up OTP Service..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file - please edit it with your settings"; \
		echo ""; \
		echo "Generate JWT_SECRET:"; \
		python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"; \
		echo ""; \
		echo "Generate API_KEY:"; \
		python3 -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(32))"; \
	else \
		echo ".env file already exists"; \
	fi

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Done!"

run:
	@echo "Starting OTP Service..."
	python3 app.py

test:
	@echo "Running API tests..."
	python test_api.py

docker-build:
	@echo "Building Docker image..."
	docker-compose build

docker-run:
	@echo "Starting service with Docker Compose..."
	docker-compose up -d
	@echo "Service started!"
	@echo "Check status: make docker-logs"
	@echo "Stop service: make docker-stop"

docker-logs:
	docker-compose logs -f

docker-stop:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-restart:
	@echo "Restarting Docker containers..."
	docker-compose restart

clean:
	@echo "Cleaning temporary files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	find . -type f -name "*.log" -delete
	@echo "Done!"

dev:
	@echo "Starting in development mode with auto-reload..."
	DEBUG=true python app.py

lint:
	@echo "Running code quality checks..."
	@command -v pylint >/dev/null 2>&1 || { echo "Installing pylint..."; pip install pylint; }
	pylint app.py || true

format:
	@echo "Formatting code..."
	@command -v black >/dev/null 2>&1 || { echo "Installing black..."; pip install black; }
	black app.py

check-health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Service not running"

generate-token:
	@echo "Generating access token..."
	@curl -s -X POST http://localhost:8000/api/v1/token \
		-H "Content-Type: application/json" \
		-d '{"api_key": "$(shell grep API_KEY .env | cut -d '=' -f2)"}' | python -m json.tool
