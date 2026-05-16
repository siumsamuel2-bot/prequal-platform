$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '6a61c06f-b011-4e5c-b2a9-e69dd59fa985'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
}

$url = "$apiUrl/api/issues/$issueId"
$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing
Write-Output $response.Content