$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'X-Paperclip-Run-Id' = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
    'Content-Type' = 'application/json'
}
$body = @{
    status = 'done'
    comment = 'Created CertificationAlerts.tsx and SubcontractorProfile.tsx components. Updated TypeScript interfaces in client.ts. Added dashboardApi.getSummary() endpoint.'
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/c85cbd37-4514-4cc2-9d74-0532a60a5873' -Headers $headers -Method Patch -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $reader.ReadToEnd() | Write-Host
}