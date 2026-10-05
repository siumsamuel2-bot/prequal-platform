. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '6a61c06f-b011-4e5c-b2a9-e69dd59fa985'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId"

Write-HeartbeatLog "Fetching issue MID-24: $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -OperationName "get-mid24-issue"
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully fetched issue in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    $response | ConvertTo-Json -Depth 10
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to fetch issue after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}