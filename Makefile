# Makefile for Launch the Nukes project
.PHONY: help setup test clean docker-build docker-up docker-down deploy-gcp local-run

# Default target
help:
	@echo "Available targets:"
	@echo "  setup       - Setup local development environment"
	@echo "  test        - Run tests"
	@echo "  clean       - Clean up temporary files"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-up   - Start services with Docker Compose"
	@echo "  docker-down - Stop Docker Compose services"
	@echo "  local-run   - Run application locally"
	@echo "  deploy-gcp  - Deploy to Google Cloud Platform"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code"

# Setup local development environment
setup:
	@echo "Setting up local development environment..."
	./setup-local.sh

# Run tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	python -m pytest tests/ --cov=. --cov-report=html --cov-report=term

# Clean up temporary files
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type f -name "*.log" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f cloudrun-*-configured.yaml

# Build Docker images
docker-build:
	@echo "Building Docker images..."
	docker-compose build

# Start services with Docker Compose
docker-up:
	@echo "Starting services with Docker Compose..."
	docker-compose up -d

# Stop Docker Compose services
docker-down:
	@echo "Stopping Docker Compose services..."
	docker-compose down

# Run application locally
local-run:
	@echo "Starting local development servers..."
	@echo "Starting Redis..."
	redis-server --daemonize yes
	@echo "Starting worker in background..."
	python worker.py --workers 2 &
	@echo "Starting Flask app..."
	python app.py

# Deploy to Google Cloud Platform
deploy-gcp:
	@echo "Deploying to Google Cloud Platform..."
	./deploy-gcp.sh

# Run linting
lint:
	@echo "Running linting..."
	python -m flake8 . --exclude=.venv,venv,__pycache__,.git --max-line-length=120

# Format code
format:
	@echo "Formatting code..."
	python -m black . --exclude='\.venv|venv|__pycache__|\.git'

# Check environment
env-check:
	@echo "Checking environment..."
	./setup-env.sh validate

# Show current configuration
show-config:
	@echo "Current configuration:"
	./setup-env.sh show

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Update dependencies
update-deps:
	@echo "Updating dependencies..."
	pip install -r requirements.txt --upgrade

# Run development server with auto-reload
dev:
	@echo "Starting development server with auto-reload..."
	export FLASK_ENV=development && python app.py

# Run production server locally
prod-local:
	@echo "Starting production server locally..."
	gunicorn -c gunicorn.conf.py app:app

# Check Redis status
redis-status:
	@echo "Checking Redis status..."
	redis-cli ping || echo "Redis is not running"

# Monitor Redis activity
redis-monitor:
	@echo "Monitoring Redis activity (Ctrl+C to stop)..."
	redis-cli monitor

# View application logs
logs:
	@echo "Viewing application logs..."
	tail -f *.log 2>/dev/null || echo "No log files found"

# Run security checks
security-check:
	@echo "Running security checks..."
	python -m safety check
	python -m bandit -r . -x .venv,venv,tests/
