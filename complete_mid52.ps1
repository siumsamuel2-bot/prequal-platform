$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "52beeae3-d249-4582-a873-0a3f9b7311e6"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId"

$body = @{
    "status" = "done"
    "comment" = "Completed implementation of Dashboard & Analytics page:

- Dashboard component with compliance overview metrics (total subs, compliance %, expiring soon, violations)
- Trend charts using Recharts wired to `/api/analytics/compliance/trends`
- CSV export functional with date range filter
- Quick-action widgets (alerts sidebar, action buttons)
- All API endpoints integrated

Code is complete and ready for integration testing. Depends on MID-46 (DB Schema) for materialized views to have data."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Patch -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}