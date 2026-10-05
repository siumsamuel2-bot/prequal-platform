. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
$issueId = 'c35b7cba-4002-49d5-9531-74c999b3cc41'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$body = @{
    agentId = $agentId
    expectedStatuses = @("todo", "backlog", "blocked")
} | ConvertTo-Json

$url = "$apiUrl/api/issues/$issueId/checkout"

Write-HeartbeatLog "Checking out issue $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -Method "POST" -OperationName "checkout-issue-$issueId" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully checked out issue in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    Write-Output $response
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to checkout issue after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}