# Prequal Platform - Production Deployment Script (PowerShell)
# This script automates the production deployment process

$ErrorActionPreference = "Stop"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Prequal Platform - Production Deploy" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Terraform
if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Terraform is not installed" -ForegroundColor Red
    exit 1
}

# Check AWS CLI
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Host "Error: AWS CLI is not installed" -ForegroundColor Red
    exit 1
}

# Check AWS credentials
try {
    $null = aws sts get-caller-identity 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: AWS credentials not configured" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error: AWS credentials not configured" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Prerequisites checked" -ForegroundColor Green
Write-Host ""

# Initialize Terraform
Write-Host "Initializing Terraform..." -ForegroundColor Yellow
terraform init -reconfigure
Write-Host "✓ Terraform initialized" -ForegroundColor Green
Write-Host ""

# Validate configuration
Write-Host "Validating Terraform configuration..." -ForegroundColor Yellow
terraform validate
Write-Host "✓ Configuration valid" -ForegroundColor Green
Write-Host ""

# Plan deployment
Write-Host "Planning deployment..." -ForegroundColor Yellow
terraform plan -out=tfplan
Write-Host "✓ Deployment plan created" -ForegroundColor Green
Write-Host ""

# Show plan summary
Write-Host "Deployment Plan Summary:" -ForegroundColor Yellow
terraform show -no-color tfplan | Select-String "^  #" | Select-Object -First 20
Write-Host ""

# Apply deployment
Write-Host "Ready to deploy to production." -ForegroundColor Yellow
$confirm = Read-Host "Do you want to continue? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Deployment cancelled" -ForegroundColor Red
    exit 0
}

Write-Host "Applying Terraform configuration..." -ForegroundColor Yellow
terraform apply tfplan

Write-Host "✓ Deployment complete" -ForegroundColor Green
Write-Host ""

# Get outputs
Write-Host "Deployment Outputs:" -ForegroundColor Yellow
Write-Host "ALB DNS Name: $(terraform output -raw alb_dns_name 2>$null || 'N/A')"
Write-Host "Database Endpoint: $(terraform output -raw db_endpoint 2>$null || 'N/A')"
Write-Host "Redis Endpoint: $(terraform output -raw redis_endpoint 2>$null || 'N/A')"
Write-Host ""

# Run health checks
Write-Host "Running post-deployment health checks..." -ForegroundColor Yellow
$healthCheckScript = "..\prequal-platform\scripts\verify-deployment.ps1"
if (Test-Path $healthCheckScript) {
    & $healthCheckScript
} else {
    Write-Host "Health check script not found, skipping..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "Deployment Successful" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
