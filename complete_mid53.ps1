$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "ddece1d6-c68a-41f9-bc2b-ec4f50ceeff4"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId"

$body = @{
    "status" = "done"
    "comment" = "## Completed: PDF Compliance Reports Generator

**Implemented:**
- PDF generation service (`app/services/pdf_service.py`) using WeasyPrint
- HTML template with: company info, compliance score, certifications table, violations table, projects list
- API endpoint: `GET /api/subcontractors/{id}/report` returns downloadable PDF
- Frontend download button on subcontractor detail page

**Dependencies added:**
- WeasyPrint>=60.0 in requirements.txt

**Files created/modified:**
- `app/services/pdf_service.py` (new)
- `app/routers/compliance.py` (added /report endpoint)
- `src/api/client.ts` (added downloadReport method)
- `src/components/SubcontractorProfile.tsx` (added Download PDF button)
- `requirements.txt` (added weasyprint)

**Note:** Batch report generation (multiple subcontractors) not implemented - can be added as follow-up task if needed."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Patch -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}