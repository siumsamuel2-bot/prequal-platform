$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'Content-Type' = 'application/json'
}
try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/agents/me' -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
}