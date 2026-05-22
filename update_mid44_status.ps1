$headers = @{
    'Authorization' = 'Bearer ' + [System.Environment]::GetEnvironmentVariable('PAPERCLIP_API_KEY')
    'X-Paperclip-Run-Id' = [System.Environment]::GetEnvironmentVariable('PAPERCLIP_RUN_ID')
    'Content-Type' = 'application/json'
}
$body = @{
    status = 'done'
    comment = 'UI Polish & UX Improvements completed:

**Loading States:**
- SubcontractorList: Added `Loading` component and `SkeletonTable` for async operations
- SubcontractorProfile: Added `Loading` component with fullScreen support
- Certifications: Added `Loading` component

**Toast Notifications:**
- DocumentUpload: Integrated `useToast` for success/error feedback instead of local state

**Responsive Design (768px+ support):**
- Layout.css: Added tablet/mobile breakpoints
- Sidebar.css: Added adaptive layout for tablet (horizontal nav) and mobile (stacked)

**Empty States:**
- Created `EmptyState` component in Loading.tsx with icon, title, description, action props
- SubcontractorList: Shows EmptyState with contextual messaging for empty lists and filtered results
- Certifications: Shows EmptyState with contextual messaging

**Existing components ready to use:**
- ErrorBoundary: wraps App.tsx
- ToastContainer: positioned top-right
- ConfirmDialog: available for destructive action confirmation'
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:3100/api/issues/2e2bdf93-2ad8-4792-8774-84c7522c3afd' -Headers $headers -Method Patch -Body $body -ErrorAction Stop
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Status: $($_.Exception.Response.StatusCode)"
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    $reader.ReadToEnd() | Write-Host
}