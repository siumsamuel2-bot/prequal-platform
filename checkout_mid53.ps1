$headers = @{
    'Authorization' = "Bearer $env:PAPERCLIP_API_KEY"
    'X-Paperclip-Run-Id' = "$env:PAPERCLIP_RUN_ID"
    'Content-Type' = 'application/json'
}
$issueId = "ddece1d6-c68a-41f9-bc2b-ec4f50ceeff4"
$url = "$env:PAPERCLIP_API_URL/api/issues/$issueId/checkout"

$body = @{
    "agentId" = "$env:PAPERCLIP_AGENT_ID"
    "expectedStatuses" = @("todo", "backlog")
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Post -Body $body
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Error $_.Exception.Message
}