. "$PSScriptRoot\scripts\heartbeat-common.ps1"

# PAPERCLIP_API_KEY is injected by the runtime; never read tokens from disk.
$commentText = @"
## Docker Image Optimization Complete

### Changes Applied

**Converted to Multi-Stage Builds:**
- Dockerfile.backend - Now uses 2-stage build (builder + production)
- Dockerfile.api - Now uses 2-stage build with virtual environment

**Improved Existing Builds:**
- Dockerfile.frontend - Added security updates, nginx user permissions
- Dockerfile (main) - Optimized layer commands

**Added .dockerignore Files:**
- .dockerignore, .dockerignore.backend, .dockerignore.frontend

### Expected Impact

| Image | Est. Before | Est. After | Reduction |
|-------|-------------|------------|-----------|
| backend | ~900MB | ~400MB | ~55% |
| api | ~800MB | ~350MB | ~56% |
| frontend | ~350MB | ~200MB | ~43% |

### Documentation

Full details in prequal-platform/DOCKER_OPTIMIZATION.md

### Status

Ready for testing.
"@

$body = @{
    comment = $commentText
} | ConvertTo-Json -Compress

Write-HeartbeatLog "Posting comment to issue $env:PAPERCLIP_TASK_ID" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri "$env:PAPERCLIP_API_URL/api/issues/$env:PAPERCLIP_TASK_ID/comments" -Headers @{
        "Authorization" = "Bearer $env:PAPERCLIP_API_KEY"
        "X-Paperclip-Run-Id" = $env:PAPERCLIP_RUN_ID
        "Content-Type" = "application/json"
    } -Method "POST" -OperationName "post-comment" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully posted comment in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to post comment after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}