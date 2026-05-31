$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
}
$issueId = "52beeae3-d249-4582-a873-0a3f9b7311e6"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId"

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}