$headers = @{'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')}
try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/agents/me' -Headers $headers -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Error: $_"
}