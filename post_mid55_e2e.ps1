$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## E2E Test Setup Complete

Created Playwright configuration (`playwright.config.ts`) and E2E test file (`e2e/user_journey.spec.ts`) covering the primary user journey:

**Test flow: registration -> login -> add subcontractor -> view compliance**

**To run E2E tests:**
```bash
npm install -D @playwright/test
npx playwright install
npx playwright test
```

**Note:** E2E tests require the full stack running:
- Backend API on port 8000
- Frontend dev server on port 5173

Created test factories in existing conftest.py for:
- Test organization creation
- Test team creation  
- Test user with org membership
- Test subcontractor creation

**Final test coverage summary:**

| Requirement | Status | Test File |
|------------|--------|-----------|
| Auth integration tests | Done | `test_auth_integration.py` |
| Subcontractor CRUD with org scoping | Done | `test_subcontractor_crud.py` |
| Alert delivery flow | Done (existing) | `test_alerts_integration.py` |
| Dashboard analytics API | Done (existing) | `test_analytics_router.py` |
| E2E: user registration -> login -> add sub -> view compliance | Config ready | `e2e/user_journey.spec.ts` |
| Test fixtures and factories | Done | `conftest.py` |

Ready for CI integration - tests can run with `pytest tests/` for backend integration tests."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}