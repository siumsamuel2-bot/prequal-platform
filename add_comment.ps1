$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'X-Paperclip-Run-Id' = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
    'Content-Type' = 'application/json'
}
$body = @{
    body = 'CI/CD Pipeline Setup is DevOps work, not Senior Engineer responsibility per AGENTS.md. Reassigning to DevOps Engineer. Senior Engineer owns frontend/backend implementation, not CI/CD infrastructure.'
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/7c2b659d-1eb3-4c5c-930d-0dc59de3dfba/comments' -Headers $headers -Method Post -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $reader.ReadToEnd() | Write-Host
}