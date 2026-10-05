. "$PSScriptRoot\heartbeat-common.ps1"

$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
$companyId = 'a8229d13-98fa-43f9-b9d3-1e662ec89105'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/companies/$companyId/issues?assigneeAgentId=$agentId&status=todo,in_progress,blocked"

Write-HeartbeatLog "Fetching agent issues" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -OperationName "fetch-my-issues"
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully fetched issues in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    $response | ConvertTo-Json -Depth 10
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to fetch issues after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}