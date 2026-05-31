$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}

$issueId = '5de0b54f-237a-4dc0-b7c5-c584392436f2'
$commentBody = @"
## Update: MID-58 Still Blocked - Second Escalation

Data Engineer run fa41301a is now "running" but has been for 25+ minutes with no work produced. Issue remains blocked - checkout returns 409.

The problem is the execution lock on the issue itself. As long as the Data Engineer's run holds the lock, I cannot checkout.

This is a systemic issue with the Data Engineer agent. Per [MID-57](/MID/issues/MID-57): "it consistently queues runs but never executes them".

@CEO - Requesting immediate intervention:
1. Cancel run fa41301a
2. Force-release the execution lock on MID-58
3. Reassign to me so I can implement the Analytics APIs

This is blocking MID-52 (Dashboard) which is done and waiting for these backend APIs.
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