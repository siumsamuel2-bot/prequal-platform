#!/bin/bash
# Prequal Platform - Production Deployment Script
# This script automates the deployment process to AWS ECS

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ECS_CLUSTER="prequal-cluster"
BACKEND_SERVICE="prequal-backend-service"
FRONTEND_SERVICE="prequal-frontend-service"
BACKEND_TASK_DEF="prequal-backend"
FRONTEND_TASK_DEF="prequal-frontend"
ECR_BACKEND=""  # Will be set from Terraform output
ECR_FRONTEND="" # Will be set from Terraform output

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Build and push Docker images
build_and_push_images() {
    local version="${1:-latest}"
    
    log_info "Building and pushing Docker images (version: $version)..."
    
    # Build backend image
    log_info "Building backend image..."
    docker build -f Dockerfile.backend.prod -t $ECR_BACKEND:$version .
    
    # Build frontend image
    log_info "Building frontend image..."
    docker build -f Dockerfile.frontend.prod -t $ECR_FRONTEND:$version .
    
    # Push backend image
    log_info "Pushing backend image..."
    docker push $ECR_BACKEND:$version
    
    # Push frontend image
    log_info "Pushing frontend image..."
    docker push $ECR_FRONTEND:$version
    
    log_info "Images built and pushed successfully"
}

# Update ECS services
update_services() {
    local version="${1:-latest}"
    
    log_info "Updating ECS services..."
    
    # Update backend service
    log_info "Updating backend service..."
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $BACKEND_SERVICE \
        --task-definition $BACKEND_TASK_DEF:$version \
        --force-new-deployment \
        --region $AWS_REGION
    
    # Update frontend service
    log_info "Updating frontend service..."
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $FRONTEND_SERVICE \
        --task-definition $FRONTEND_TASK_DEF:$version \
        --force-new-deployment \
        --region $AWS_REGION
    
    log_info "Services updated successfully"
}

# Wait for deployment
wait_for_deployment() {
    log_info "Waiting for deployment to complete..."
    
    # Wait for backend
    log_info "Waiting for backend service..."
    aws ecs wait services-stable \
        --cluster $ECS_CLUSTER \
        --services $BACKEND_SERVICE \
        --region $AWS_REGION
    
    # Wait for frontend
    log_info "Waiting for frontend service..."
    aws ecs wait services-stable \
        --cluster $ECS_CLUSTER \
        --services $FRONTEND_SERVICE \
        --region $AWS_REGION
    
    log_info "Deployment completed successfully"
}

# Health check
health_check() {
    local endpoint="${1:-}"
    
    if [ -z "$endpoint" ]; then
        log_warn "No endpoint provided, skipping health check"
        return
    fi
    
    log_info "Running health checks..."
    
    # Check backend health
    if curl -f -s "${endpoint}/api/health" > /dev/null; then
        log_info "Backend health check passed"
    else
        log_error "Backend health check failed"
        exit 1
    fi
    
    # Check frontend health
    if curl -f -s "${endpoint}/" > /dev/null; then
        log_info "Frontend health check passed"
    else
        log_error "Frontend health check failed"
        exit 1
    fi
    
    log_info "All health checks passed"
}

# Rollback deployment
rollback() {
    local version="${1}"
    
    if [ -z "$version" ]; then
        log_error "Rollback version not specified"
        exit 1
    fi
    
    log_warn "Rolling back to version: $version"
    
    # Update services with previous version
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $BACKEND_SERVICE \
        --task-definition $BACKEND_TASK_DEF:$version \
        --force-new-deployment \
        --region $AWS_REGION
    
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $FRONTEND_SERVICE \
        --task-definition $FRONTEND_TASK_DEF:$version \
        --force-new-deployment \
        --region $AWS_REGION
    
    log_info "Rollback completed"
}

# Main deployment function
deploy() {
    local version="${1:-latest}"
    local skip_build="${2:-false}"
    local endpoint="${3:-}"
    
    log_info "Starting deployment (version: $version)..."
    
    if [ "$skip_build" = "false" ]; then
        build_and_push_images "$version"
    fi
    
    update_services "$version"
    wait_for_deployment
    
    if [ -n "$endpoint" ]; then
        health_check "$endpoint"
    fi
    
    log_info "Deployment completed successfully!"
}

# Print usage
usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  deploy [version]     Deploy application (default: latest)"
    echo "  rollback [version]   Rollback to specific version"
    echo "  health [endpoint]    Run health checks"
    echo "  status               Show deployment status"
    echo ""
    echo "Options:"
    echo "  --skip-build         Skip building and pushing images"
    echo "  --endpoint           Endpoint for health checks"
    echo ""
    echo "Examples:"
    echo "  $0 deploy"
    echo "  $0 deploy v1.2.3"
    echo "  $0 rollback v1.2.2"
    echo "  $0 health https://prequal.yourcompany.com"
}

# Show status
status() {
    log_info "Deployment status:"
    
    echo ""
    echo "Backend Service:"
    aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $BACKEND_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].deployments[0]' \
        --output table
    
    echo ""
    echo "Frontend Service:"
    aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $FRONTEND_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].deployments[0]' \
        --output table
}

# Main
case "${1:-deploy}" in
    deploy)
        check_prerequisites
        deploy "${2:-latest}" "${3:-false}" "${4:-}"
        ;;
    rollback)
        check_prerequisites
        rollback "${2}"
        ;;
    health)
        health_check "${2}"
        ;;
    status)
        status
        ;;
    build)
        check_prerequisites
        build_and_push_images "${2:-latest}"
        ;;
    update)
        check_prerequisites
        update_services "${2:-latest}"
        ;;
    *)
        usage
        exit 1
        ;;
esac
