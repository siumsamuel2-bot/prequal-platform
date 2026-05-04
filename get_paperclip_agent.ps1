# Output the environment variables
Write-Host "PAPERCLIP_API_KEY: $env:PAPERCLIP_API_KEY"
Write-Host "PAPERCLIP_RUN_ID: $env:PAPERCLIP_RUN_ID"
Write-Host "PAPERCLIP_API_URL: $env:PAPERCLIP_API_URL"

# Construct the API URL
$apiUrl = "$env:PAPERCLIP_API_URL/api/agents/me"

# Prepare headers with authorization
$headers = @{
    Authorization = "Bearer $env:PAPERCLIP_API_KEY"
}

# Make the GET request
try {
    $response = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Get
    Write-Host "`nAPI Response:"
    $response | ConvertTo-Json -Depth 5 | Write-Host
}
catch {
    Write-Error "`nError making request: $_"
}