. "$PSScriptRoot\heartbeat-common.ps1"

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

Write-HeartbeatLog "Updating MID-24 to done status" "INFO"
$startTime = Get-Date

try {
    $response = Invoke-HeartbeatRequest -Uri $url -Headers $headers -Method "PATCH" -OperationName "update-mid24-done" -Body $body
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Successfully updated MID-24 in $([Math]::Round($duration.TotalSeconds, 2))s" "INFO"
    Write-Output $response
} catch {
    $duration = (Get-Date) - $startTime
    Write-HeartbeatLog "Failed to update MID-24 after $([Math]::Round($duration.TotalSeconds, 2))s: $_" "ERROR"
    throw $_
}