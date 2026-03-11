.PHONY: all build up down logs test clean dev help

# Default target
all: build

# Build all containers
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d

# Start in foreground
up-fg:
	docker-compose up

# Stop all services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# View specific service logs
logs-%:
	docker-compose logs -f $*

# Run tests
test: test-go test-python

test-go:
	cd coordinator && go test ./...

test-python:
	cd agents && python -m pytest tests/ -v

# Development mode
dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Build and run locally (without Docker)
run-local: build-local
	./coordinator/nexus-coordinator

build-local:
	cd coordinator && go build -o nexus-coordinator .

# Install Go dependencies
deps-go:
	cd coordinator && go mod download && go mod tidy

# Install Python dependencies
deps-python:
	cd agents && pip install -r requirements.txt

# Clean build artifacts
clean:
	docker-compose down -v
	rm -f coordinator/nexus-coordinator
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Initialize project (first time setup)
init:
	@echo "Creating .env file from example..."
	@cp -n .env.example .env || true
	@echo "Creating data directories..."
	@mkdir -p data credentials
	@echo "Done! Edit .env with your configuration."

# Redis CLI access
redis-cli:
	docker-compose exec redis redis-cli

# Database shell
db-shell:
	docker-compose exec coordinator sqlite3 /data/nexus.db

# Restart a specific service
restart-%:
	docker-compose restart $*

# Rebuild and restart a specific service
rebuild-%:
	docker-compose build $*
	docker-compose up -d $*

# Show service status
status:
	docker-compose ps

# Help
help:
	@echo "NEXUS Makefile commands:"
	@echo ""
	@echo "  make build        - Build all Docker containers"
	@echo "  make up           - Start all services (detached)"
	@echo "  make up-fg        - Start all services (foreground)"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View all logs"
	@echo "  make logs-<svc>   - View specific service logs"
	@echo "  make test         - Run all tests"
	@echo "  make dev          - Start in development mode"
	@echo "  make clean        - Clean build artifacts and volumes"
	@echo "  make init         - Initialize project (first time setup)"
	@echo "  make status       - Show service status"
	@echo "  make redis-cli    - Access Redis CLI"
	@echo "  make restart-<svc>- Restart a specific service"
	@echo "  make rebuild-<svc>- Rebuild and restart a service"
	@echo ""
