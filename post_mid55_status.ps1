$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Status - Starting Integration Tests

Analyzed existing test infrastructure and found:
- pytest with async support (`pytest-asyncio`) already configured
- SQLite test database with analytics views for testing
- `AsyncClient` from httpx for API testing
- Some existing tests: `test_analytics_router.py`, `test_alerts.py`, `test_credential_upload.py`

Missing test coverage per requirements:
1. **Auth integration tests** - No auth tests exist, will create `test_auth.py`
2. **Subcontractor CRUD tests** - Need to check if covered
3. **Alert delivery flow tests** - `test_alerts.py` exists, need to review coverage
4. **Dashboard analytics API** - `test_analytics_router.py` exists and covers this
5. **E2E tests (Playwright)** - Need to set up Playwright and create E2E tests

Starting with auth integration tests first."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}