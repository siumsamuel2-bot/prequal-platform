$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$response = Invoke-WebRequest -Uri "$apiUrl/api/agents/me/inbox-lite" -Headers $headers -UseBasicParsing
Write-Output $response.Content
