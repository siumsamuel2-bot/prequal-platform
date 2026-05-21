$headers = @{
    "Authorization" = "Bearer $env:PAPERCLIP_API_KEY"
    "X-Paperclip-Run-Id" = "$env:PAPERCLIP_RUN_ID"
    "Content-Type" = "application/json"
}

$body = @"
{"agentId":"cf66724f-10d9-49ef-87fa-3b5989c26bb6","expectedStatuses":["todo","backlog","blocked"]}
"@

$response = Invoke-RestMethod -Uri "http://127.0.0.1:3100/api/issues/2e2bdf93-2ad8-4792-8774-84c7522c3afd/checkout" -Method POST -Headers $headers -Body $body
$response | ConvertTo-Json -Depth 10