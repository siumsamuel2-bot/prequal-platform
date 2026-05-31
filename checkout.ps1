$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}
$body = @{
    agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
    expectedStatuses = @('todo', 'backlog', 'blocked')
} | ConvertTo-Json

try {
    $apiUrl = $env:PAPERCLIP_API_URL
    $response = Invoke-RestMethod -Uri "$apiUrl/api/issues/68b07ab2-0037-4fd3-aa0b-5512046e4748/checkout" -Headers $headers -Method Post -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}