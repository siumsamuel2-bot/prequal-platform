$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'X-Paperclip-Run-Id' = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
    'Content-Type' = 'application/json'
}
$body = @{
    agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
    expectedStatuses = @('todo', 'backlog', 'blocked')
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/47b0dfa4-8367-44f2-a165-af6d47c4d84e/checkout' -Headers $headers -Method Post -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}