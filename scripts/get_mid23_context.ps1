$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '4a984d62-5fc0-4777-97fc-99503ede41b1'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/heartbeat-context"
$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing
Write-Output $response.Content