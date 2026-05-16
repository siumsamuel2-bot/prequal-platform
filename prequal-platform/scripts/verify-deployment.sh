#!/bin/bash
# Prequal Platform - Staging Deployment Verification Script
# Run this after deployment to verify all services are healthy

set -e

COMPOSE_FILE="docker-compose.staging.yml"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Prequal Platform - Health Check"
echo "======================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running or not installed${NC}"
    exit 1
fi

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Docker Compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    local timeout=5
    
    if curl --max-time $timeout --silent "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $service is healthy"
        return 0
    else
        echo -e "${RED}✗${NC} $service is not responding"
        return 1
    fi
}

# Check Docker containers status
echo "Container Status:"
echo "----------------"
docker-compose -f $COMPOSE_FILE ps
echo ""

# Check individual services
echo "Service Health Checks:"
echo "---------------------"

# Backend check
check_service "Backend (8000)" "http://localhost:8000/health" || true

# Frontend check  
check_service "Frontend (3000)" "http://localhost:3000" || true

# Database check
if docker-compose -f $COMPOSE_FILE exec -T db pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Database is ready"
else
    echo -e "${RED}✗${NC} Database is not ready"
fi

# Redis check
if docker-compose -f $COMPOSE_FILE exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is responding"
else
    echo -e "${RED}✗${NC} Redis is not responding"
fi

echo ""
echo "Resource Usage:"
echo "--------------"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    prequal-backend-staging prequal-frontend-staging prequal-db-staging prequal-redis-staging 2>/dev/null || echo "Stats not available"

echo ""
echo "======================================"
echo "Verification Complete"
echo "======================================"
