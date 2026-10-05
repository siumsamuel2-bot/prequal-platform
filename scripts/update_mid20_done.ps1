. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = 'c35b7cba-4002-49d5-9531-74c999b3cc41'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$comment = "MID-20 (FastAPI-Database Integration): COMPLETED. Verified FastAPI backend is fully implemented with all models, routers, schemas. Added pyjwt>=2.8.0 to requirements.txt. All 30+ API routes registered correctly."

$body = @{
    status = "done"
    comment = $comment
} | ConvertTo-Json

$url = "$apiUrl/api/issues/$issueId"

Write-HeartbeatLog "Updating MID-20 to done status" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -Method "PATCH" -OperationName "update-mid20-done" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully updated MID-20 in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    Write-Output $response
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to update MID-20 after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}