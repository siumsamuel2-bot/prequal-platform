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
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/c85cbd37-4514-4cc2-9d74-0532a60a5873/checkout' -Headers $headers -Method Post -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    Write-Host "Error: $_"
}