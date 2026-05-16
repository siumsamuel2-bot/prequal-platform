$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$runId = $env:PAPERCLIP_RUN_ID
$issueId = '6a61c06f-b011-4e5c-b2a9-e69dd59fa985'

$headers = @{
    "Authorization" = "Bearer $apiKey"
    "X-Paperclip-Run-Id" = $runId
    "Content-Type" = "application/json"
}

$comment = "MID-24 (Frontend Scaffolding: React + Dashboard Shell): COMPLETED. Verified frontend scaffolding is fully functional. React+Vite+TypeScript project builds successfully with no type errors. All components present: App.tsx with routing, Layout/Sidebar/Header shell, Dashboard, Login, Register, Certifications, Violations, SubcontractorList pages. API client configured."

$body = @{
    status = "done"
    comment = $comment
} | ConvertTo-Json

$url = "$apiUrl/api/issues/$issueId"
$response = Invoke-WebRequest -Uri $url -Headers $headers -Method PATCH -Body $body -UseBasicParsing
Write-Output $response.Content