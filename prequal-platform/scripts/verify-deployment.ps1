# Prequal Platform - Staging Deployment Verification Script (PowerShell)
# Run this after deployment to verify all services are healthy

$ErrorActionPreference = "Stop"

$COMPOSE_FILE = "docker-compose.staging.yml"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Prequal Platform - Health Check" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker is not running or not installed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Docker is not running or not installed" -ForegroundColor Red
    exit 1
}

# Check if compose file exists
if (-not (Test-Path $COMPOSE_FILE)) {
    Write-Host "Docker Compose file not found: $COMPOSE_FILE" -ForegroundColor Red
    exit 1
}

# Function to check service health
function Check-Service {
    param(
        [string]$Name,
        [string]$Url,
        [int]$Timeout = 5
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $Timeout -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 304) {
            Write-Host "✓ $Name is healthy" -ForegroundColor Green
            return $true
        } else {
            Write-Host "✗ $Name returned $($response.StatusCode)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "✗ $Name is not responding" -ForegroundColor Red
        return $false
    }
}

# Check Docker containers status
Write-Host "Container Status:" -ForegroundColor Yellow
Write-Host "----------------" -ForegroundColor Yellow
docker-compose -f $COMPOSE_FILE ps
Write-Host ""

# Check individual services
Write-Host "Service Health Checks:" -ForegroundColor Yellow
Write-Host "---------------------" -ForegroundColor Yellow

# Backend check
Check-Service -Name "Backend (8000)" -Url "http://localhost:8000/health"

# Frontend check
Check-Service -Name "Frontend (3000)" -Url "http://localhost:3000"

# Database check
try {
    $null = docker-compose -f $COMPOSE_FILE exec -T db pg_isready -U postgres
    Write-Host "✓ Database is ready" -ForegroundColor Green
} catch {
    Write-Host "✗ Database is not ready" -ForegroundColor Red
}

# Redis check
try {
    $redisPing = docker-compose -f $COMPOSE_FILE exec -T redis redis-cli ping
    if ($redisPing -match "PONG") {
        Write-Host "✓ Redis is responding" -ForegroundColor Green
    } else {
        Write-Host "✗ Redis is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ Redis is not responding" -ForegroundColor Red
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Verification Complete" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
