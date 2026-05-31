$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}