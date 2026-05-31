$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "52beeae3-d249-4582-a873-0a3f9b7311e6"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Additional Fixes Completed

Enhanced the Dashboard implementation:

1. **Trend data now fetches from backend**: Changed from mock data (`Math.random()`) to calling `/api/analytics/compliance/trends?days={exportRange}` for real compliance trend data
2. **CSV export uses selected date range**: The export now passes `expiration_bucket=${exportRange}` to filter the export to the selected 30/60/90 day period

Dashboard now fully wired:
- Summary metrics from `/api/dashboard/summary`
- Alerts from `/api/compliance/alerts`
- Trend data from `/api/analytics/compliance/trends?days={30|60|90}`
- CSV export from `/api/analytics/compliance/export?format=csv&expiration_bucket={30|60|90}`

Ready for integration testing once MID-46 (DB Schema) is complete."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}