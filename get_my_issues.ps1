$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'Content-Type' = 'application/json'
}
$url = 'http://127.0.0.1:3100/api/companies/a8229d13-98fa-43f9-b9d3-1e662ec89105/issues?assigneeAgentId=cf66724f-10d9-49ef-87fa-3b5989c26bb6&status=todo,in_progress'
try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
}