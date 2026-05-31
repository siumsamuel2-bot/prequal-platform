$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "52beeae3-d249-4582-a873-0a3f9b7311e6"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Dashboard Implementation Complete

All core functionality has been implemented and verified:

| Requirement | Status | Implementation |
|------------|--------|----------------|
| Dashboard renders with real compliance metrics | Done | `/api/dashboard/summary` via `dashboardApi.getSummary()` |
| Charts show 30/60/90 day compliance trends | Done | `/api/analytics/compliance/trends?days={30|60|90}` - now wired correctly with field mapping `compliance_percentage`, `open_violations`, `expired_certifications` |
| CSV export downloads from the browser | Done | `/api/analytics/compliance/export?format=csv&expiration_bucket={30|60|90}` respects the selected date range |
| Quick-action widgets | Done | Alerts sidebar and action buttons implemented |
| API endpoints for aggregated data | Done | Backend has `/dashboard/summary`, `/compliance/alerts`, `/analytics/compliance/trends`, `/analytics/compliance/export` |

**Bugs Fixed:**
1. Dashboard.tsx called non-existent `dashboardApi.getAlerts()` - now uses `complianceApi.getAlerts()`
2. Trend chart used mock data - now fetches from `/api/analytics/compliance/trends`
3. CSV export didn't use selected date range - now passes `expiration_bucket` parameter
4. Backend `/compliance/alerts` missing `days_until_expiration` field - now included
5. Frontend field mapping corrected to match backend response (`compliance_percentage`, `open_violations`, `expired_certifications`)

**Remaining dependency:** MID-46 (DB Schema) must be complete for materialized views (`mv_compliance_trends`, etc.) to have data."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}