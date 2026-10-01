#!/bin/bash
# Docker Build Script with Layer Caching
# Uses BuildKit for improved layer caching across builds
#
# Features:
# - BuildKit enabled for better cache management
# - Cache-from pulls existing layers to avoid rebuilding unchanged layers
# - Cache-to exports cache for future builds (CI/CD)
# - Build arguments for environment-specific builds
# - Parallel builds for multi-service projects

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
TARGET="${TARGET:-all}"
ENVIRONMENT="${ENVIRONMENT:-development}"
CACHE_FROM=""
CACHE_TO=""
NO_CACHE=false
PULL=false
OUTPUT_FILE="docker-build.log"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--target)
            TARGET="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --cache-from)
            CACHE_FROM="$2"
            shift 2
            ;;
        --cache-to)
            CACHE_TO="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --pull)
            PULL=true
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-t|--target] [-e|--environment] [--cache-from] [--cache-to] [--no-cache] [--pull]"
            exit 1
            ;;
    esac
done

# Enable BuildKit
export DOCKER_BUILDKIT=1
echo -e "${CYAN}BuildKit enabled: DOCKER_BUILDKIT=1${NC}"

# Build configuration
declare -A BUILD_CONFIG
BUILD_CONFIG[backend]="Dockerfile.backend:prequal-backend:PYTHON_VERSION=3.11,ENVIRONMENT=${ENVIRONMENT}"
BUILD_CONFIG[frontend]="Dockerfile.frontend:prequal-frontend:NODE_VERSION=18,ENVIRONMENT=${ENVIRONMENT}"
BUILD_CONFIG[api]="Dockerfile.api:prequal-api:PYTHON_VERSION=3.11,ENVIRONMENT=${ENVIRONMENT}"

# Function to build a Docker image
build_image() {
    local dockerfile=$1
    local tag=$2
    local build_args=$3
    local context="${4:-.}"
    
    local build_cmd="docker build"
    build_cmd="$build_cmd -f $dockerfile"
    build_cmd="$build_cmd -t $tag"
    
    # Add build args
    if [ -n "$build_args" ]; then
        IFS=',' read -ra ARGS <<< "$build_args"
        for arg in "${ARGS[@]}"; do
            build_cmd="$build_cmd --build-arg $arg"
        done
    fi
    
    # Add cache-from if specified
    if [ -n "$CACHE_FROM" ]; then
        echo -e "${CYAN}  Using cache from: $CACHE_FROM${NC}"
        build_cmd="$build_cmd --cache-from $CACHE_FROM"
    fi
    
    # Add cache-to if specified (for CI/CD)
    if [ -n "$CACHE_TO" ]; then
        echo -e "${CYAN}  Exporting cache to: $CACHE_TO${NC}"
        build_cmd="$build_cmd --cache-to type=inline,mode=max"
    fi
    
    # Add no-cache flag if specified
    if [ "$NO_CACHE" = true ]; then
        echo -e "${YELLOW}  Building without cache (fresh build)${NC}"
        build_cmd="$build_cmd --no-cache"
    fi
    
    # Add pull flag if specified
    if [ "$PULL" = true ]; then
        echo -e "${CYAN}  Pulling base images${NC}"
        build_cmd="$build_cmd --pull"
    fi
    
    # Add progress output
    build_cmd="$build_cmd --progress=plain"
    
    # Add context
    build_cmd="$build_cmd $context"
    
    echo -e "${CYAN}  Running: $build_cmd${NC}"
    
    # Execute build and capture time
    local start_time=$(date +%s)
    if eval "$build_cmd" 2>&1 | tee -a "$OUTPUT_FILE"; then
        local end_time=$(date +%s)
        local build_time=$((end_time - start_time))
        local image_size=$(docker images "$tag" --format "{{.Size}}")
        echo -e "${GREEN}  ✓ Build successful in ${build_time}s${NC}"
        echo -e "${CYAN}  Image size: $image_size${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Build failed${NC}"
        return 1
    fi
}

# Main execution
echo -e "${CYAN}=== Docker Build with Layer Caching ===${NC}"
echo -e "Environment: $ENVIRONMENT"
echo -e "Target: $TARGET"
echo -e "Cache From: ${CACHE_FROM:-none}"
echo -e "Cache To: ${CACHE_TO:-none}"
echo -e "No Cache: $NO_CACHE"
echo -e "Pull Base Images: $PULL"
echo ""

# Initialize report
REPORT="# Docker Build Report\n"
REPORT+="Generated: $(date '+%Y-%m-%d %H:%M:%S')\n\n"
REPORT+="## Build Configuration\n"
REPORT+="- **Environment:** $ENVIRONMENT\n"
REPORT+="- **BuildKit:** Enabled\n"
REPORT+="- **Cache From:** ${CACHE_FROM:-none}\n"
REPORT+="- **Cache To:** ${CACHE_TO:-none}\n"
REPORT+="- **No Cache:** $NO_CACHE\n"
REPORT+="- **Pull Base Images:** $PULL\n\n"
REPORT+="## Build Results\n\n"
REPORT+="| Target | Status | Size | Build Time |\n"
REPORT+="|--------|--------|------|------------|\n"

RESULTS=()
TARGETS_TO_BUILD=()

# Determine targets
if [ "$TARGET" = "all" ]; then
    TARGETS_TO_BUILD=("backend" "frontend" "api")
else
    TARGETS_TO_BUILD=("$TARGET")
fi

# Build each target
for target_name in "${TARGETS_TO_BUILD[@]}"; do
    if [ -n "${BUILD_CONFIG[$target_name]}" ]; then
        IFS=':' read -r dockerfile tag build_args <<< "${BUILD_CONFIG[$target_name]}"
        full_tag="$tag:$ENVIRONMENT"
        
        echo -e "${CYAN}Building $target_name...${NC}"
        
        if build_image "$dockerfile" "$full_tag" "$build_args"; then
            image_size=$(docker images "$full_tag" --format "{{.Size}}")
            RESULTS+=("$target_name:success:$image_size")
            REPORT+="| $full_tag | ✓ | $image_size | - |\n"
        else
            RESULTS+=("$target_name:failed:N/A")
            REPORT+="| $full_tag | ✗ | N/A | N/A |\n"
        fi
        echo ""
    else
        echo -e "${YELLOW}Unknown target: $target_name${NC}"
    fi
done

# Add optimization info to report
REPORT+="\n## Layer Caching Strategy\n\n"
REPORT+="### BuildKit Features Used\n"
REPORT+="1. **BuildKit Enabled** - Modern Docker build engine with improved caching\n"
REPORT+="2. **Cache-from** - Pulls existing layers to avoid rebuilding unchanged layers\n"
REPORT+="3. **Cache-to** - Exports build cache for future builds (CI/CD)\n"
REPORT+="4. **Inline Cache** - Stores cache metadata in the image itself\n\n"
REPORT+="### How It Works\n"
REPORT+="- **First build:** All layers are built from scratch\n"
REPORT+="- **Subsequent builds:**\n"
REPORT+="  - Unchanged layers (e.g., base image, dependencies) are pulled from cache\n"
REPORT+="  - Changed layers (e.g., application code) are rebuilt\n"
REPORT+="  - Cache is exported for future builds\n\n"

# Save report
echo -e "$REPORT" > "${OUTPUT_FILE%.log}.md"
echo -e "${GREEN}Report saved to ${OUTPUT_FILE%.log}.md${NC}"

# Display summary
echo -e "${CYAN}\n=== Summary ===${NC}"
successful=0
total=${#TARGETS_TO_BUILD[@]}

for result in "${RESULTS[@]}"; do
    IFS=':' read -r name status size <<< "$result"
    if [ "$status" = "success" ]; then
        ((successful++))
    fi
done

if [ $successful -eq $total ]; then
    echo -e "${GREEN}Successful builds: $successful / $total${NC}"
    exit 0
else
    echo -e "${YELLOW}Successful builds: $successful / $total${NC}"
    exit 1
fi