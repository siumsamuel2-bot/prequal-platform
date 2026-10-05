. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '64595933-62e0-4843-8dd3-a1bc8b3336ff'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/heartbeat-context"

Write-HeartbeatLog "Fetching heartbeat context for issue: $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -OperationName "heartbeat-context-$issueId"
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully fetched heartbeat context in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    $response | ConvertTo-Json -Depth 10
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to fetch heartbeat context after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}