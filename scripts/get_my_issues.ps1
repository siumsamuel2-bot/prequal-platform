$apiUrl = $env:PAPERCLIP_API_URL
$apiKey = $env:PAPERCLIP_API_KEY
$agentId = 'cf66724f-10d9-49ef-87fa-3b5989c26bb6'
$companyId = 'a8229d13-98fa-43f9-b9d3-1e662ec89105'

$headers = @{
    "Authorization" = "Bearer $apiKey"
}

$url = "$apiUrl/api/companies/$companyId/issues?assigneeAgentId=$agentId&status=todo,in_progress,blocked"
$response = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing
Write-Output $response.Content
