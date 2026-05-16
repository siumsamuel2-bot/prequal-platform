$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '64595933-62e0-4843-8dd3-a1bc8b3336ff'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/heartbeat-context"
$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing
Write-Output $response.Content