$headers = @{'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')}
$headers['X-Paperclip-Run-Id'] = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
$apiUrl = $env:PAPERCLIP_API_URL

# Checkout MID-42
$issueId = "e20357b5-c738-4a7a-8c69-bc7d309c8968"

$checkoutBody = @{
    agentId = "cf66724f-10d9-49ef-87fa-3b5989c26bb6"
    expectedStatuses = @("todo", "backlog")
} | ConvertTo-Json -Depth 10

Write-Host "Checking out MID-42..."
$checkout = Invoke-RestMethod -Uri "$apiUrl/api/issues/$issueId/checkout" -Method POST -Headers $headers -Body $checkoutBody -ContentType "application/json" -ErrorAction Stop
$checkout | ConvertTo-Json -Depth 5