. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = 'da2f53fe-ec9e-45ba-a1fd-dd23c612d5e6'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/heartbeat-context"

Write-HeartbeatLog "Fetching heartbeat context for MID-17 issue: $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -OperationName "heartbeat-context-mid17"
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully fetched heartbeat context in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    $response | ConvertTo-Json -Depth 10
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to fetch heartbeat context after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}