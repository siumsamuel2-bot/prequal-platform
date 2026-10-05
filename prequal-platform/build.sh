#!/bin/bash
# Build script for Prequal Platform Docker images
# Optimized for CI/CD with layer caching and parallel builds

set -e

# Enable BuildKit for better caching and parallel builds
export DOCKER_BUILDKIT=1

# Configuration
REGISTRY=${REGISTRY:-""}
IMAGE_PREFIX=${IMAGE_PREFIX:-"prequal"}
TAG=${TAG:-"latest"}
PLATFORM=${PLATFORM:-"linux/amd64"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            BUILD_BACKEND=true
            shift
            ;;
        --frontend)
            BUILD_FRONTEND=true
            shift
            ;;
        --all)
            BUILD_BACKEND=true
            BUILD_FRONTEND=true
            shift
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --load-cache)
            LOAD_CACHE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend       Build backend image only"
            echo "  --frontend      Build frontend image only"
            echo "  --all           Build all images (default)"
            echo "  --platform      Target platform (default: linux/amd64)"
            echo "  --tag           Image tag (default: latest)"
            echo "  --registry      Container registry (optional)"
            echo "  --push          Push images to registry"
            echo "  --load-cache    Load build cache from registry"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Default to building all if nothing specified
if [ -z "$BUILD_BACKEND" ] && [ -z "$BUILD_FRONTEND" ]; then
    BUILD_BACKEND=true
    BUILD_FRONTEND=true
fi

log_info "Starting build process with BuildKit enabled"
log_info "Platform: $PLATFORM"
log_info "Tag: $TAG"

# Function to build image with cache optimization
build_image() {
    local name=$1
    local dockerfile=$2
    local target=$3
    local image_name="${IMAGE_PREFIX}-${name}"
    
    if [ -n "$REGISTRY" ]; then
        image_name="${REGISTRY}/${image_name}"
    fi
    
    log_info "Building ${name} image: ${image_name}:${TAG}"
    
    # Build command with cache optimization
    BUILD_CMD="docker build"
    BUILD_CMD+=" --platform ${PLATFORM}"
    BUILD_CMD+=" --build-arg BUILDKIT_INLINE_CACHE=1"
    BUILD_CMD+=" --cache-from ${image_name}:latest"
    
    if [ -n "$target" ]; then
        BUILD_CMD+=" --target ${target}"
    fi
    
    if [ "$PUSH" = true ]; then
        BUILD_CMD+=" --push"
    fi
    
    BUILD_CMD+=" -t ${image_name}:${TAG}"
    BUILD_CMD+=" -t ${image_name}:latest"
    BUILD_CMD+=" -f ${dockerfile} ."
    
    eval $BUILD_CMD
    
    log_info "Successfully built ${name} image"
}

# Build backend
if [ "$BUILD_BACKEND" = true ]; then
    log_info "Building backend image..."
    build_image "backend" "Dockerfile.backend.prod" "production"
fi

# Build frontend
if [ "$BUILD_FRONTEND" = true ]; then
    log_info "Building frontend image..."
    build_image "frontend" "Dockerfile.frontend.prod" "production"
fi

log_info "Build completed successfully!"

# Show image sizes
log_info "Image sizes:"
docker images | grep "${IMAGE_PREFIX}-" | awk '{print $1, $2, $7}'