$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = 'c35b7cba-4002-49d5-9531-74c999b3cc41'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$comment = "MID-20 (FastAPI-Database Integration): COMPLETED. Verified FastAPI backend is fully implemented with all models, routers, schemas. Added pyjwt>=2.8.0 to requirements.txt. All 30+ API routes registered correctly."

$body = @{
    status = "done"
    comment = $comment
} | ConvertTo-Json

$url = "$apiUrl/api/issues/$issueId"
$response = Invoke-WebRequest -Uri $url -Headers $headers -Method PATCH -Body $body -UseBasicParsing
Write-Output $response.Content