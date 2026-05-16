$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'X-Paperclip-Run-Id' = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
    'Content-Type' = 'application/json'
}
$body = @{
    status = 'done'
    comment = 'PatternOCRExtractor implemented with pattern-based cert extraction, date parsing, PDF/image OCR, confidence scoring. Tests added. Unable to verify API status update due to 500 errors on PATCH.'
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/47b0dfa4-8367-44f2-a165-af6d47c4d84e' -Headers $headers -Method Patch -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $reader.ReadToEnd() | Write-Host
}