$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "ddece1d6-c68a-41f9-bc2b-ec4f50ceeff4"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/comments"

$body = @{
    "body" = "## Status - Starting PDF Report Generator

Analyzing requirements for PDF Compliance Reports:
- PDF generation using WeasyPrint (HTML-to-PDF)
- Report template with: sub info, active certs, compliance status, history
- API endpoint: `GET /api/subcontractors/{id}/report` returning PDF
- Batch report for org-level compliance
- Frontend download button on subcontractor detail page

Implementation plan:
1. Add WeasyPrint dependency to requirements.txt
2. Create PDF generation service (`app/services/pdf_service.py`)
3. Create API endpoint in compliance router
4. Add download button to SubcontractorProfile component
5. Add API client method for report download

Starting with backend service and API endpoint."
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}