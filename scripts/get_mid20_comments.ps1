. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = 'c35b7cba-4002-49d5-9531-74c999b3cc41'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/comments"

Write-HeartbeatLog "Fetching comments for MID-20 issue: $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -OperationName "get-mid20-comments"
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully fetched comments in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    $response | ConvertTo-Json -Depth 10
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to fetch comments after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}