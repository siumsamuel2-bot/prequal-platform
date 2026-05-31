$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "dbaffd07-2a8f-4c86-aca7-7ca95a645926"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Progress Update

Created auth integration tests (`test_auth_integration.py`) covering:
- User registration (valid, duplicate email)
- Login (valid credentials, invalid password, nonexistent user)
- OAuth2 token endpoint
- Token refresh
- /me endpoint (with and without token)
- Logout

Existing test coverage confirmed:
- Dashboard analytics API: `test_analytics_router.py`
- Alert delivery flow: `test_alerts_integration.py`
- Credential upload: `test_credential_upload.py`

Still needed:
1. **Subcontractor CRUD integration tests** - Need to create `test_subcontractor_crud.py`
2. **Playwright E2E setup** - Need to install Playwright and create E2E test for: registration -> login -> add subcontractor -> view compliance
3. **Test factories/fixtures** - May need additional factory helpers for test data

Working on subcontractor CRUD tests next."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}