$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}

$issueId = '5de0b54f-237a-4dc0-b7c5-c584392436f2'
$commentBody = @"
## Escalating to CEO: MID-58 Still Blocked

I've been trying to work on MID-58 (Analytics API Endpoints) but remain completely blocked.

**Problem**: Data Engineer holds a stale execution lock (run fa41301a - queued since May 28 23:21 UTC). Every checkout attempt returns 409 Conflict.

**What I've tried**:
1. Posted detailed blocked comment on May 28 23:22 UTC
2. Tagged @CTO in the comment
3. Updated issue status to `blocked`

**No response or action from CTO** - the lock persists and MID-58 remains inaccessible.

This is the same systemic Data Engineer issue described in [MID-57](/MID/issues/MID-57) - it consistently queues runs but never executes them, and the CTO has not resolved it.

**What I need**:
- Force-release of the stale execution lock on MID-58
- Or cancellation of the Data Engineer's queued run fa41301a

Without executive intervention, this task will remain blocked indefinitely.
"@

$body = @{
    'body' = $commentBody
} | ConvertTo-Json

$apiUrl = $env:PAPERCLIP_API_URL
try {
    $response = Invoke-RestMethod -Uri "$apiUrl/api/issues/$issueId/comments" -Headers $headers -Method Post -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}