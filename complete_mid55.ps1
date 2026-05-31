$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId"

$body = @{
    "status" = "done"
    "comment" = "## Completed: Integration & End-to-End Testing for Core Flows

**Created test files:**
- `tests/test_auth_integration.py` - Auth flow tests (register, login, token refresh, logout)
- `tests/test_subcontractor_crud.py` - Subcontractor CRUD with org scoping tests
- `e2e/user_journey.spec.ts` - Playwright E2E test for primary user journey
- `playwright.config.ts` - Playwright configuration

**Existing tests utilized:**
- `tests/test_analytics_router.py` - Dashboard analytics API
- `tests/test_alerts_integration.py` - Alert delivery flow
- `tests/test_credential_upload.py` - Credential upload flow

**Test execution:**
```bash
# Backend integration tests
cd prequal-platform
venv\Scripts\python.exe -m pytest tests/ -v

# E2E tests (requires full stack)
npm install -D @playwright/test
npx playwright test
```

All core application flows now have test coverage."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Patch -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}