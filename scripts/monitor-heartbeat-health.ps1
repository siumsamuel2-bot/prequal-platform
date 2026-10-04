# Monitor Heartbeat Health Script
# Detect and alert on silent heartbeat adapter failures
# Run periodically to check agent heartbeat health

param(
    [int]$SilentThresholdMinutes = 60,
    [string]$OutputLogPath = "C:\Users\siums\AppData\Local\Temp\opencode\heartbeat-monitor.log",
    [string]$AlertOutputDir = "artifacts\heartbeat"
)

# Import shared utilities
. "$PSScriptRoot\heartbeat-common.ps1"

# Alias Write-Log to shared logger (using custom path)
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    Write-HeartbeatLog $Message $Level $OutputLogPath
}

# Wrapper using shared request with retry
function Get-JsonWebRequestWithRetry {
    param(
        [string]$Uri,
        [hashtable]$Headers,
        [string]$OperationName
    )
    return Invoke-HeartbeatRequest -Uri $Uri -Headers $Headers -OperationName $OperationName -Method Get -TimeoutSec 30
}

Write-Log "Starting heartbeat health check" "INFO"
$startTime = Get-Date

try {
    $agentsUrl = "$env:PAPERCLIP_API_URL/api/companies/$env:PAPERCLIP_COMPANY_ID/agents"
    $headers = @{
        "Authorization" = "Bearer $env:PAPERCLIP_API_KEY"
        "X-Paperclip-Run-Id" = $env:PAPERCLIP_RUN_ID
    }
    Write-Log "Fetching agents from API: $agentsUrl" "INFO"
    $agents = Get-JsonWebRequestWithRetry -Uri $agentsUrl -Headers $headers -OperationName "fetch-agents"
    Write-Log "Fetched $($agents.Count) agents" "INFO"

    $healthyCount = 0
    $unhealthyCount = 0
    $silentAgents = @()

    foreach ($agent in $agents) {
        $lastHeartbeat = $agent.lastHeartbeatAt
        if ($null -eq $lastHeartbeat) {
            Write-Log "Agent $($agent.name) has no heartbeat record" "WARN"
            $unhealthyCount++
            continue
        }
        $heartbeatTime = [DateTime]::Parse($lastHeartbeat)
        $timeSinceHeartbeat = (Get-Date) - $heartbeatTime
        if ($timeSinceHeartbeat.TotalMinutes -gt $SilentThresholdMinutes) {
            Write-Log "Agent $($agent.name) (ID: $($agent.id)) silent for $([Math]::Round($timeSinceHeartbeat.TotalMinutes,1)) minutes" "WARN"
            $silentAgents += $agent
            $unhealthyCount++
        } else {
            $healthyCount++
        }
    }

    $duration = (Get-Date) - $startTime
    Write-Log "Health check complete: $healthyCount healthy, $unhealthyCount unhealthy (took $([Math]::Round($duration.TotalSeconds,2))s)" "INFO"

    if ($silentAgents.Count -gt 0) {
        Write-Log "ALERT: $($silentAgents.Count) agent(s) exceeded silent threshold" "ALERT"
        $alertPayload = @{
            "alertType" = "silent_heartbeat"
            "timestamp" = (Get-Date -Format "o")
            "thresholdMinutes" = $SilentThresholdMinutes
            "affectedAgents" = $silentAgents | Select-Object id, name, lastHeartbeatAt
        } | ConvertTo-Json -Depth 3
        if (-not (Test-Path -LiteralPath $AlertOutputDir)) {
            New-Item -ItemType Directory -Path $AlertOutputDir -Force | Out-Null
        }
        $alertPath = Join-Path $AlertOutputDir "heartbeat-alert-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
        $alertPayload | Out-File -FilePath $alertPath -Encoding utf8
        Write-Log "Alert written to $alertPath" "INFO"
    }
    if ($silentAgents.Count -gt 0) { exit 1 }
    exit 0
} catch {
    $duration = (Get-Date) - $startTime
    Write-Log "Health check failed after $([Math]::Round($duration.TotalSeconds,2))s: $_" "ERROR"
    exit 1
}
