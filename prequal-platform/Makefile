.PHONY: help build build-backend buildfrontend clean test scan push dev prod

# Default target
help:
	@echo "Prequal Platform - Docker Build Targets"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build           Build all images (backend + frontend)"
	@echo "  build-backend   Build backend image only"
	@echo "  build-frontend  Build frontend image only"
	@echo "  build-dev       Build development images"
	@echo "  build-prod      Build production images"
	@echo "  clean           Remove all built images and containers"
	@echo "  clean-cache     Clear Docker build cache"
	@echo "  dev             Start development environment"
	@echo "  prod            Start production environment"
	@echo "  stop            Stop all containers"
	@echo "  logs            Show container logs"
	@echo "  test            Run basic image tests"
	@echo "  scan            Run security scan on images"
	@echo "  push            Push images to registry"
	@echo "  sizes           Show image sizes"
	@echo ""

# Enable BuildKit
export DOCKER_BUILDKIT = 1

# Image configuration
REGISTRY ?= ghcr.io
IMAGE_PREFIX ?= prequal
TAG ?= latest
PLATFORM ?= linux/amd64

# Build all images
build: build-backend build-frontend
	@echo "All images built successfully"

# Build backend image
build-backend:
	@echo "Building backend image..."
	docker build \
		--platform $(PLATFORM) \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--cache-from $(IMAGE_PREFIX)-backend:latest \
		-t $(IMAGE_PREFIX)-backend:$(TAG) \
		-t $(IMAGE_PREFIX)-backend:latest \
		-f Dockerfile.backend.prod \
		--target production \
		.

# Build frontend image
build-frontend:
	@echo "Building frontend image..."
	docker build \
		--platform $(PLATFORM) \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--cache-from $(IMAGE_PREFIX)-frontend:latest \
		-t $(IMAGE_PREFIX)-frontend:$(TAG) \
		-t $(IMAGE_PREFIX)-frontend:latest \
		-f Dockerfile.frontend.prod \
		--target production \
		.

# Build development images
build-dev:
	@echo "Building development images..."
	docker-compose build

# Build production images
build-prod: build-backend build-frontend

# Clean up images and containers
clean:
	@echo "Removing containers..."
	docker-compose down --remove-orphans || true
	@echo "Removing images..."
	docker rmi $(IMAGE_PREFIX)-backend:latest 2>/dev/null || true
	docker rmi $(IMAGE_PREFIX)-backend:$(TAG) 2>/dev/null || true
	docker rmi $(IMAGE_PREFIX)-frontend:latest 2>/dev/null || true
	docker rmi $(IMAGE_PREFIX)-frontend:$(TAG) 2>/dev/null || true
	@echo "Cleanup complete"

# Clear Docker build cache
clean-cache:
	@echo "Clearing Docker build cache..."
	docker builder prune -f
	@echo "Cache cleared"

# Start development environment
dev:
	@echo "Starting development environment..."
	docker-compose up -d
	@echo "Development environment started"
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"

# Start production environment
prod:
	@echo "Starting production environment..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "Production environment started"

# Stop all containers
stop:
	@echo "Stopping all containers..."
	docker-compose down
	docker-compose -f docker-compose.prod.yml down || true

# Show container logs
logs:
	docker-compose logs -f

# Follow backend logs
logs-backend:
	docker-compose logs -f backend

# Follow frontend logs
logs-frontend:
	docker-compose logs -f frontend

# Run basic tests on images
test: build
	@echo "Running image tests..."
	@echo "Checking backend image..."
	docker run --rm $(IMAGE_PREFIX)-backend:latest python --version
	@echo "Checking frontend image..."
	docker run --rm $(IMAGE_PREFIX)-frontend:latest nginx -v
	@echo "All tests passed"

# Run security scan
scan: build
	@echo "Running security scan..."
	@echo "Note: Install Trivy from https://aquasecurity.github.io/trivy/"
	@echo "Then run: trivy image $(IMAGE_PREFIX)-backend:latest"
	@echo "Then run: trivy image $(IMAGE_PREFIX)-frontend:latest"

# Push images to registry
push: build
	@echo "Pushing images to $(REGISTRY)..."
	docker tag $(IMAGE_PREFIX)-backend:$(TAG) $(REGISTRY)/$(IMAGE_PREFIX)-backend:$(TAG)
	docker tag $(IMAGE_PREFIX)-backend:latest $(REGISTRY)/$(IMAGE_PREFIX)-backend:latest
	docker tag $(IMAGE_PREFIX)-frontend:$(TAG) $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(TAG)
	docker tag $(IMAGE_PREFIX)-frontend:latest $(REGISTRY)/$(IMAGE_PREFIX)-frontend:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-backend:$(TAG)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-backend:latest
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-frontend:$(TAG)
	docker push $(REGISTRY)/$(IMAGE_PREFIX)-frontend:latest
	@echo "Images pushed successfully"

# Show image sizes
sizes:
	@echo "Docker Image Sizes:"
	docker images | grep $(IMAGE_PREFIX)- || echo "No images found"

# Health check
health:
	@echo "Checking container health..."
	docker-compose ps
	@echo ""
	@echo "Backend health:"
	curl -s http://localhost:8000/health || echo "Backend not responding"
	@echo ""
	@echo "Frontend health:"
	curl -s http://localhost:5173 || echo "Frontend not responding"

# Rebuild specific service
rebuild-backend:
	docker-compose build --no-cache backend
	docker-compose up -d backend

rebuild-frontend:
	docker-compose build --no-cache frontend
	docker-compose up -d frontend

# Database operations
db-migrate:
	docker-compose exec backend alembic upgrade head

db-backup:
	@echo "Creating database backup..."
	docker-compose exec db pg_dump -U postgres prequal > backup_$(shell date +%Y%m%d_%H%M%S).sql

db-restore:
	@echo "Restoring database from backup..."
	@echo "Usage: make db-restore BACKUP=backup_20240101_120000.sql"
	cat $(BACKUP) | docker-compose exec -T db psql -U postgres -d prequal

# Interactive shell
shell-backend:
	docker-compose exec backend /bin/sh

shell-frontend:
	docker-compose exec frontend /bin/sh

shell-db:
	docker-compose exec db psql -U postgres -d prequal