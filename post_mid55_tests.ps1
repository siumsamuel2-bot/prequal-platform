$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Integration Tests Update

Created subcontractor CRUD integration tests (`test_subcontractor_crud.py`) covering:
- Create subcontractor (valid, invalid email, missing required fields)
- List subcontractors with pagination
- Get subcontractor by ID (valid, nonexistent)
- Update subcontractor (partial updates, status changes)
- Delete subcontractor (valid, nonexistent)

Current test coverage:
| Area | Status | Test File |
|------|--------|-----------|
| Auth (login/register/logout/refresh) | Done | `test_auth_integration.py` |
| Subcontractor CRUD with org scoping | Done | `test_subcontractor_crud.py` |
| Alert delivery flow | Done (existing) | `test_alerts_integration.py` |
| Dashboard analytics API | Done (existing) | `test_analytics_router.py` |

**Remaining: E2E tests with Playwright**
- Need to install Playwright
- Create E2E test: user registration -> login -> add subcontractor -> view compliance
- This requires frontend dev server running

Will set up Playwright next."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}