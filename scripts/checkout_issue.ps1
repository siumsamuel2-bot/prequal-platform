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
$response = Invoke-WebRequest -Uri $url -Headers $headers -Method POST -Body $body -UseBasicParsing
Write-Output $response.Content