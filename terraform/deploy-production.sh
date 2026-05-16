#!/bin/bash
# Prequal Platform - Production Deployment Script
# This script automates the production deployment process

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "Prequal Platform - Production Deploy"
echo "======================================"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Terraform
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"
echo ""

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init -reconfigure
echo -e "${GREEN}✓ Terraform initialized${NC}"
echo ""

# Validate configuration
echo -e "${YELLOW}Validating Terraform configuration...${NC}"
terraform validate
echo -e "${GREEN}✓ Configuration valid${NC}"
echo ""

# Plan deployment
echo -e "${YELLOW}Planning deployment...${NC}"
terraform plan -out=tfplan
echo -e "${GREEN}✓ Deployment plan created${NC}"
echo ""

# Show plan summary
echo -e "${YELLOW}Deployment Plan Summary:${NC}"
terraform show -no-color tfplan | grep "^  #" | head -20 || true
echo ""

# Apply deployment
echo -e "${YELLOW}Ready to deploy to production.${NC}"
read -p "Do you want to continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 0
fi

echo -e "${YELLOW}Applying Terraform configuration...${NC}"
terraform apply tfplan

echo -e "${GREEN}✓ Deployment complete${NC}"
echo ""

# Get outputs
echo -e "${YELLOW}Deployment Outputs:${NC}"
echo "ALB DNS Name: $(terraform output -raw alb_dns_name || echo 'N/A')"
echo "Database Endpoint: $(terraform output -raw db_endpoint || echo 'N/A')"
echo "Redis Endpoint: $(terraform output -raw redis_endpoint || echo 'N/A')"
echo ""

# Run health checks
echo -e "${YELLOW}Running post-deployment health checks...${NC}"
if [ -f "../prequal-platform/scripts/verify-deployment.sh" ]; then
    ../prequal-platform/scripts/verify-deployment.sh
else
    echo -e "${YELLOW}Health check script not found, skipping...${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}Deployment Successful${NC}"
echo "======================================"
