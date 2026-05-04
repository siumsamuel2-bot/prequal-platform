# Get inbox items for the agent
$url = "$env:PAPERCLIP_API_URL/api/agents/me/inbox-lite"
$headers = @{
    Authorization = "Bearer $env:PAPERCLIP_API_KEY"
}

# Make the GET request
try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get
    Write-Host "`nInbox Items:"
    $response | ConvertTo-Json -Depth 5 | Write-Host
}
catch {
    Write-Error "`nError making request: $_"
}