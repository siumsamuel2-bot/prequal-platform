$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '64595933-62e0-4843-8dd3-a1bc8b3336ff'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$commentText = @'
## MID-21 Complete: Frontend Scaffolding Done

Successfully built the React frontend foundation for the Prequal compliance dashboard.

### What was delivered:

1. **React + TypeScript + Vite** project initialized
2. **React Router** configured for dashboard views (/dashboard, /subcontractors, /compliance, /reports, /settings)
3. **Layout components** created:
   - `Layout.tsx` - main layout wrapper
   - `Sidebar.tsx` - navigation with active state highlighting
   - `Header.tsx` - search bar and user menu with notifications
4. **API client layer** (`src/api/client.ts`) configured:
   - Bearer token authentication
   - Methods for subcontractors, compliance, and auth APIs
   - Properly targets FastAPI backend at `/api`
5. **Authentication pages** functional:
   - Login with username/password
   - Register with email, name, password validation
   - Token storage in localStorage

### Fixes applied:
- Renamed `babel.config.js` to `babel.config.cjs` to fix ESM/CommonJS conflict
- Connected Sidebar logout button to `logout()` function

### Test results:
- All 7 tests passing
- Ready for feature development

### For Junior Engineers:
- API client is at `src/api/client.ts` - use `authApi`, `subcontractorApi`, `complianceApi` for backend calls
- Auth utilities are at `src/utils/auth.ts` - use `login()`, `logout()`, `isAuthenticated()`, `getToken()`
- All protected routes go through `PrivateRoute` wrapper in `App.tsx`
'@

$body = @{
    status = "done"
    comment = $commentText
} | ConvertTo-Json -Depth 10

$url = "$apiUrl/api/issues/$issueId"
$response = Invoke-WebRequest -Uri $url -Headers $headers -Method PATCH -Body $body -UseBasicParsing
Write-Output $response.StatusCode