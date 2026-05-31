$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "ddece1d6-c68a-41f9-bc2b-ec4f50ceeff4"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = '## PDF Report Generator - Progress

**Backend implementation:**
- Created `app/services/pdf_service.py` with WeasyPrint HTML-to-PDF generation
- PDF includes: company info, compliance score, active certifications table, violations table, assigned projects
- Added WeasyPrint to requirements.txt

**API endpoint:**
- `GET /api/subcontractors/{id}/report` returns PDF download

**Frontend implementation:**
- Added `downloadReport()` method to `subcontractorApi` in api/client.ts
- Added Download PDF button to SubcontractorProfile component header
- Button appears for existing subcontractors (not new ones)

**Note:** WeasyPrint requires system dependencies (GTK3, Pango, etc.) for PDF rendering. These are typically installed on Linux systems. For Windows development, you may need WSL or a Docker container.

**Remaining:**
- Batch report generation for org-level compliance
- CSS styling refinement if needed'
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}