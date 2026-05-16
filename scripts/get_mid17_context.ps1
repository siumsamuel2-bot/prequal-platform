$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = 'da2f53fe-ec9e-45ba-a1fd-dd23c612d5e6'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId/heartbeat-context"
$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing
Write-Output $response.Content