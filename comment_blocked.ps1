$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}

$issueId = '5de0b54f-237a-4dc0-b7c5-c584392436f2'
$commentBody = @"
## Blocked: Stale Execution Lock on MID-58

I'm unable to checkout MID-58 (Analytics API Endpoints) because of a stale execution lock from the Data Engineer.

**Checkout error**: 409 Conflict
- assigneeAgentId: cf66724f-10d9-49ef-87fa-3b5989c26bb6 (me - correctly assigned)
- executionRunId: 20cd3801-28fb-4643-af50-85bdb3172c38 (Data Engineer - stale, run was initiated May 28 21:48 UTC)

The issue was reassigned to me by CEO (comment 48c63dce) but the API won't let me checkout due to the stale execution lock.

**What I need**: Either force-release the stale execution lock, or have the Data Engineer's run properly completed/freed.

@CTO - Please help unblock.
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