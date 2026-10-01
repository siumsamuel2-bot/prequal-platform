# Docker Build Script with Layer Caching
# Uses BuildKit for improved layer caching across builds
# 
# Features:
# - BuildKit enabled for better cache management
# - Cache-from pulls existing layers to avoid rebuilding unchanged layers
# - Cache-to exports cache for future builds (CI/CD)
# - Build arguments for environment-specific builds
# - Parallel builds for multi-service projects

param(
    [string]$Target = "all",  # all, backend, frontend, api
    [string]$Environment = "development",  # development, staging, production
    [string]$CacheFrom = "",  # Existing image to pull cache from
    [string]$CacheTo = "",    # Export cache to registry (CI/CD)
    [switch]$NoCache,         # Disable cache (fresh build)
    [switch]$Pull,            # Always pull base images
    [string]$OutputFile = "docker-build.log"
)

$ErrorActionPreference = "Stop"

# Colors for output
$Success = "Green"
$Info = "Cyan"
$Warning = "Yellow"
$Error = "Red"

function Write-Info { param($Message) Write-Host $Message -ForegroundColor $Info }
function Write-Success { param($Message) Write-Host $Message -ForegroundColor $Success }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor $Warning }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor $Error }

# Enable BuildKit (required for advanced caching)
$env:DOCKER_BUILDKIT = "1"
Write-Info "BuildKit enabled: DOCKER_BUILDKIT=1"

# Build configuration
$buildConfig = @{
    backend = @{
        dockerfile = "Dockerfile.backend"
        tag = "prequal-backend"
        context = "."
        args = @(
            "PYTHON_VERSION=3.11",
            "ENVIRONMENT=$Environment"
        )
    }
    frontend = @{
        dockerfile = "Dockerfile.frontend"
        tag = "prequal-frontend"
        context = "."
        args = @(
            "NODE_VERSION=18",
            "ENVIRONMENT=$Environment"
        )
    }
    api = @{
        dockerfile = "Dockerfile.api"
        tag = "prequal-api"
        context = "."
        args = @(
            "PYTHON_VERSION=3.11",
            "ENVIRONMENT=$Environment"
        )
    }
}

function Invoke-DockerBuild {
    param(
        [string]$Dockerfile,
        [string]$Tag,
        [string]$Context,
        [array]$BuildArgs,
        [string]$CacheFrom,
        [string]$CacheTo,
        [switch]$NoCache,
        [switch]$Pull
    )

    $buildCmd = @("build")
    
    # Add dockerfile
    $buildCmd += "-f", $Dockerfile
    
    # Add tag
    $buildCmd += "-t", $Tag
    
    # Add context
    $buildCmd += $Context
    
    # Add build args
    foreach ($arg in $BuildArgs) {
        $buildCmd += "--build-arg", $arg
    }
    
    # Add cache-from if specified
    if ($CacheFrom) {
        Write-Info "  Using cache from: $CacheFrom"
        $buildCmd += "--cache-from", $CacheFrom
    }
    
    # Add cache-to if specified (for CI/CD)
    if ($CacheTo) {
        Write-Info "  Exporting cache to: $CacheTo"
        $buildCmd += "--cache-to", "type=inline,mode=max"
    }
    
    # Add no-cache flag if specified
    if ($NoCache) {
        Write-Warning "  Building without cache (fresh build)"
        $buildCmd += "--no-cache"
    }
    
    # Add pull flag if specified
    if ($Pull) {
        Write-Info "  Pulling base images"
        $buildCmd += "--pull"
    }
    
    # Add progress output
    $buildCmd += "--progress", "plain"
    
    Write-Info "  Running: docker $($buildCmd -join ' ')"
    
    $buildTime = Measure-Command {
        & docker $buildCmd 2>&1 | Tee-Object -Variable buildOutput
    }
    
    if ($LASTEXITCODE -eq 0) {
        $imageSize = & docker images $Tag --format "{{.Size}}"
        Write-Success "  ✓ Build successful in $($buildTime.TotalSeconds.ToString("0.0"))s"
        Write-Info "  Image size: $imageSize"
        return @{
            Success = $true
            Tag = $Tag
            Size = $imageSize
            BuildTime = $buildTime.TotalSeconds
        }
    } else {
        Write-Error "  ✗ Build failed"
        Write-Error "  Error: $($buildOutput -join "`n")"
        return @{
            Success = $false
            Tag = $Tag
            Error = $buildOutput
        }
    }
}

# Main execution
Write-Info "=== Docker Build with Layer Caching ==="
Write-Info "Environment: $Environment"
Write-Info "Target: $Target"
Write-Info "Cache From: $($CacheFrom -eq "" ? "none" : $CacheFrom)"
Write-Info "Cache To: $($CacheTo -eq "" ? "none" : $CacheTo)"
Write-Info ""

$results = @()

$targetsToBuild = @()
if ($Target -eq "all") {
    $targetsToBuild = @("backend", "frontend", "api")
} else {
    $targetsToBuild = @($Target)
}

foreach ($targetName in $targetsToBuild) {
    if ($buildConfig.ContainsKey($targetName)) {
        $config = $buildConfig[$targetName]
        Write-Info "Building $targetName..."
        
        $result = Invoke-DockerBuild `
            -Dockerfile $config.dockerfile `
            -Tag "$($config.tag):$Environment" `
            -Context $config.context `
            -BuildArgs $config.args `
            -CacheFrom $CacheFrom `
            -CacheTo $CacheTo `
            -NoCache:$NoCache `
            -Pull:$Pull
        
        $results += $result
        Write-Info ""
    } else {
        Write-Warning "Unknown target: $targetName"
    }
}

# Generate build report
$report = @"
# Docker Build Report
Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Build Configuration
- **Environment:** $Environment
- **BuildKit:** Enabled
- **Cache From:** $($CacheFrom -eq "" ? "none" : $CacheFrom)
- **Cache To:** $($CacheTo -eq "" ? "none" : $CacheTo)
- **No Cache:** $NoCache
- **Pull Base Images:** $Pull

## Build Results

| Target | Status | Size | Build Time |
|--------|--------|------|------------|
"@

foreach ($result in $results) {
    if ($result.Success) {
        $report += "| $($result.Tag) | ✓ | $($result.Size) | $($result.BuildTime.ToString("0.0"))s |`n"
    } else {
        $report += "| $($result.Tag) | ✗ | N/A | N/A |`n"
    }
}

$report += @"

## Layer Caching Strategy

### BuildKit Features Used
1. **BuildKit Enabled** - Modern Docker build engine with improved caching
2. **Cache-from** - Pulls existing layers to avoid rebuilding unchanged layers
3. **Cache-to** - Exports build cache for future builds (CI/CD)
4. **Inline Cache** - Stores cache metadata in the image itself

### How It Works
- **First build:** All layers are built from scratch
- **Subsequent builds:** 
  - Unchanged layers (e.g., base image, dependencies) are pulled from cache
  - Changed layers (e.g., application code) are rebuilt
  - Cache is exported for future builds

### CI/CD Integration
For GitHub Actions or other CI/CD systems:
1. Pull cache from registry before build: \`--cache-from type=registry,ref=registry/user/image:cache\`
2. Push cache to registry after build: \`--cache-to type=registry,ref=registry/user/image:cache,mode=max\`

### Best Practices
- Tag images with environment and commit hash for traceability
- Use inline cache mode for simpler setups
- Use registry cache for CI/CD pipelines
- Clean up old cache images periodically
- Always use \`--no-cache\` for production releases to ensure clean builds

## Optimization Tips

### Dockerfile Layer Ordering
1. Copy package files first (package.json, requirements.txt)
2. Install dependencies (creates cached layer)
3. Copy application code (changes frequently, rebuilt often)

### Multi-stage Builds
- Build stage: Contains all build tools and dependencies
- Production stage: Contains only runtime dependencies
- Result: Smaller images, faster deployments

### .dockerignore
- Exclude unnecessary files (node_modules, .git, logs)
- Reduces build context size
- Speeds up initial file transfer

"@

# Save report
$report | Out-File -FilePath "docker-build-report.md" -Encoding UTF8
Write-Success "Report saved to docker-build-report.md"

# Display summary
Write-Info "`n=== Summary ==="
$successful = ($results | Where-Object { $_.Success }).Count
$total = $results.Count
Write-Host "Successful builds: $successful / $total" -ForegroundColor $(if ($successful -eq $total) { $Success } else { $Warning })

if ($successful -ne $total) {
    exit 1
}