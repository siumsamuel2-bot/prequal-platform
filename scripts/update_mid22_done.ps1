. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '38eaeb8b-270a-41c4-a64e-5b9b27b1ee85'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$commentText = @'
## MID-22 Complete: Frontend-Backend Integration Done

Fixed the API client to properly connect the React frontend to the FastAPI backend.

### Fixes applied:

1. **Fixed authApi.register return type** (`src/api/client.ts:82-83`)
   - Backend returns `{access_token, token_type}` 
   - Client was incorrectly expecting `{id, email, name}`
   - Now correctly typed to match FastAPI response

### Integration verified:

- Frontend API client is correctly configured to hit `/api` endpoints
- Vite proxy is set up to forward `/api` requests to `http://localhost:8000`
- CORS is configured on FastAPI to allow `localhost:3000` and `localhost:5173`
- Auth endpoints (`/api/auth/login`, `/api/auth/register`) return correct token format
- All data endpoints (subcontractors, contractors, certifications, violations, compliance) are available

### For Junior Engineers:
- The API client is at `src/api/client.ts` - uses Bearer token auth
- Login works with hardcoded credentials: `admin` / `password`
- Registration returns an access_token for subsequent requests
- All API responses match the TypeScript interfaces defined in `client.ts`
'@

$body = @{
    status = "done"
    comment = $commentText
} | ConvertTo-Json -Depth 10

$url = "$apiUrl/api/issues/$issueId"

Write-HeartbeatLog "Updating MID-22 to done status" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -Method "PATCH" -OperationName "update-mid22-done" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully updated MID-22 in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    Write-Output $response
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to update MID-22 after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}