$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}

$issueId = '68b07ab2-0037-4fd3-aa0b-5512046e4748'
$apiUrl = $env:PAPERCLIP_API_URL
try {
    $response = Invoke-RestMethod -Uri "$apiUrl/api/issues/$issueId/release" -Headers $headers -Method Post -Body '{}' -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}