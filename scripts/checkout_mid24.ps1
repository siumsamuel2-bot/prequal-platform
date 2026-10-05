. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
$issueId = '6a61c06f-b011-4e5c-b2a9-e69dd59fa985'

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

Write-HeartbeatLog "Checking out MID-24 issue $issueId" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -Method "POST" -OperationName "checkout-mid24-$issueId" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully checked out MID-24 in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    Write-Output $response
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to checkout MID-24 after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}