$headers = @{
    'Authorization' = 'Bearer ' + $env:PAPERCLIP_API_KEY
    'X-Paperclip-Run-Id' = $env:PAPERCLIP_RUN_ID
    'Content-Type' = 'application/json'
}

$issueId = '5de0b54f-237a-4dc0-b7c5-c584392436f2'
$body = @{
    'assigneeAgentId' = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
} | ConvertTo-Json

$apiUrl = $env:PAPERCLIP_API_URL
try {
    $response = Invoke-RestMethod -Uri "$apiUrl/api/issues/$issueId" -Headers $headers -Method Patch -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}