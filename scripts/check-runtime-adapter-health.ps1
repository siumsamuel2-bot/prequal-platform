# Runtime Adapter Health Check Script
# Detect runtime adapter failures early: validate each agent's configured model
# against the live adapter model catalog and flag agents stuck in error state.
# Runs alongside the heartbeat health check in the monitoring CI pipeline.

param(
    [string]$AdapterType = "opencode_local",
    [int]$MinGraceSec = 120,
    [int]$MinTimeoutSec = 600,
    [string]$OutputLogPath = "C:\Users\siums\AppData\Local\Temp\opencode\adapter-health.log",
    [string]$AlertOutputDir = "artifacts\adapter-health"
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

Write-Log "Starting runtime adapter health check (adapterType=$AdapterType)" "INFO"
$startTime = Get-Date

if (-not $env:PAPERCLIP_API_URL -or -not $env:PAPERCLIP_API_KEY -or -not $env:PAPERCLIP_COMPANY_ID) {
    Write-Log "SKIP: PAPERCLIP_API_URL, PAPERCLIP_API_KEY, or PAPERCLIP_COMPANY_ID not set; runtime adapter health check cannot run" "WARN"
    exit 0
}

try {
    $headers = @{
        "Authorization" = "Bearer $env:PAPERCLIP_API_KEY"
        "X-Paperclip-Run-Id" = $env:PAPERCLIP_RUN_ID
    }

    $modelsUrl = "$env:PAPERCLIP_API_URL/api/companies/$env:PAPERCLIP_COMPANY_ID/adapters/$AdapterType/models"
    $models = Get-JsonWebRequestWithRetry -Uri $modelsUrl -Headers $headers -OperationName "fetch-adapter-models"
    $availableModels = @($models | ForEach-Object { $_.id })
    Write-Log "Adapter catalog has $($availableModels.Count) available models" "INFO"

    $agentsUrl = "$env:PAPERCLIP_API_URL/api/companies/$env:PAPERCLIP_COMPANY_ID/agents"
    $agents = Get-JsonWebRequestWithRetry -Uri $agentsUrl -Headers $headers -OperationName "fetch-agents"
    Write-Log "Fetched $($agents.Count) agents" "INFO"

    $failures = @()
    $warnings = @()
    $healthyCount = 0

    foreach ($agent in $agents) {
        if ($agent.adapterType -ne $AdapterType) { continue }

        $agentName = $agent.name
        $adapterConfig = $agent.adapterConfig
        if ($null -eq $adapterConfig) { $adapterConfig = @{} }

        if ($agent.status -eq "error") {
            $failures += [PSCustomObject]@{ agent = $agentName; agentId = $agent.id; check = "agent_status"; detail = "Agent status is 'error' (runtime adapter failure)" }
            Write-Log "FAIL: Agent $agentName status is 'error'" "ERROR"
        }

        $model = $adapterConfig.model
        if ([string]::IsNullOrWhiteSpace($model)) {
            $failures += [PSCustomObject]@{ agent = $agentName; agentId = $agent.id; check = "model_configured"; detail = "No model configured in adapterConfig" }
            Write-Log "FAIL: Agent $agentName has no model configured" "ERROR"
        } elseif ($availableModels -notcontains $model) {
            $failures += [PSCustomObject]@{ agent = $agentName; agentId = $agent.id; check = "model_available"; detail = "Configured model '$model' is not in the available model catalog" }
            Write-Log "FAIL: Agent $agentName model '$model' not in available catalog" "ERROR"
        }

        $grace = $adapterConfig.graceSec
        if ($null -eq $grace -or $grace -lt $MinGraceSec) {
            $warnings += [PSCustomObject]@{ agent = $agentName; agentId = $agent.id; check = "graceSec"; detail = "graceSec=$grace below minimum $MinGraceSec" }
            Write-Log "WARN: Agent $agentName graceSec=$grace below minimum $MinGraceSec" "WARN"
        }

        $timeout = $adapterConfig.timeoutSec
        if ($null -eq $timeout -or $timeout -lt $MinTimeoutSec) {
            $warnings += [PSCustomObject]@{ agent = $agentName; agentId = $agent.id; check = "timeoutSec"; detail = "timeoutSec=$timeout below minimum $MinTimeoutSec" }
            Write-Log "WARN: Agent $agentName timeoutSec=$timeout below minimum $MinTimeoutSec" "WARN"
        }

        $agentFailures = @($failures | Where-Object { $_.agentId -eq $agent.id })
        if ($agentFailures.Count -eq 0) {
            $healthyCount++
            Write-Log "OK: Agent $agentName model '$model' available" "INFO"
        }
    }

    $duration = (Get-Date) - $startTime
    Write-Log "Runtime adapter health check complete: $healthyCount healthy, $($failures.Count) failures, $($warnings.Count) warnings (took $([Math]::Round($duration.TotalSeconds,2))s)" "INFO"

    if ($failures.Count -gt 0) {
        Write-Log "ALERT: $($failures.Count) runtime adapter failure(s) detected" "ALERT"
        $alertPayload = @{
            "alertType" = "runtime_adapter_failure"
            "timestamp" = (Get-Date -Format "o")
            "adapterType" = $AdapterType
            "availableModelCount" = $availableModels.Count
            "failures" = $failures
            "warnings" = $warnings
        } | ConvertTo-Json -Depth 4
        if (-not (Test-Path -LiteralPath $AlertOutputDir)) {
            New-Item -ItemType Directory -Path $AlertOutputDir -Force | Out-Null
        }
        $alertPath = Join-Path $AlertOutputDir "adapter-health-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
        $alertPayload | Out-File -FilePath $alertPath -Encoding utf8
        Write-Log "Alert written to $alertPath" "INFO"
        exit 1
    }

    exit 0
} catch {
    $duration = (Get-Date) - $startTime
    Write-Log "Runtime adapter health check failed after $([Math]::Round($duration.TotalSeconds,2))s: $_" "ERROR"
    exit 1
}
