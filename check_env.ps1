$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
}
$apiUrl = $env:PAPERCLIP_API_URL
$issueId = "00e797ca-c388-4c7c-86ba-676d5c175269"
$response = Invoke-RestMethod -Uri "$apiUrl/api/issues/$issueId/comments" -Headers $headers
$response | ConvertTo-Json -Depth 10