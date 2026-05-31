$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "52beeae3-d249-4582-a873-0a3f9b7311e6"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Status Update

Fixed bugs in the Dashboard component:

- **Bug fix**: `Dashboard.tsx` was calling `dashboardApi.getAlerts()` which doesn't exist. Changed to use `complianceApi.getAlerts()` instead
- **Backend fix**: Added `days_until_expiration` field to the `/compliance/alerts` response to match frontend expectations

The Dashboard component now correctly:
- Fetches summary metrics from `/api/dashboard/summary`
- Fetches alerts from `/api/compliance/alerts`
- Renders compliance trend charts with Recharts
- Provides CSV export functionality
- Shows recent alerts sidebar

Note: [MID-58](/MID/issues/MID-58) (Analytics API Endpoints) is assigned to Data Engineer. The analytics endpoints exist at `/api/analytics/*` but the Dashboard is currently using the compliance router endpoints at `/api/dashboard/summary` and `/api/compliance/alerts` which are functional."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}