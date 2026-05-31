$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
}
$issueId = "MID-46"
$url = "$env:PAPERCLIP_API_URL/api/issues?identifier=$issueId"

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}