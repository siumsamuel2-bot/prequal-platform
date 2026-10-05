# Heartbeat Common Module
# Shared retry and logging utilities for heartbeat scripts

$Script:RetryMaxRetries = 3
$Script:RetryBaseDelay = 1
$Script:RetryMaxDelay = 30

function Set-HeartbeatRetryConfig {
    param(
        [int]$MaxRetries = 3,
        [int]$BaseDelaySeconds = 1,
        [int]$MaxDelaySeconds = 30
    )
    $Script:RetryMaxRetries = $MaxRetries
    $Script:RetryBaseDelay = $BaseDelaySeconds
    $Script:RetryMaxDelay = $MaxDelaySeconds
}

function Write-HeartbeatLog {
    param(
        [string]$Message,
        [string]$Level = "INFO",
        [string]$LogPath = "C:\Users\siums\AppData\Local\Temp\opencode\heartbeat.log"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    $logDir = Split-Path -Parent $LogPath
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    Add-Content -Path $LogPath -Value $logEntry
    switch ($Level) {
        "ERROR" { Write-Error $logEntry; break }
        "WARN" { Write-Warning $logEntry; break }
        "ALERT" { Write-Warning "ALERT: $Message"; break }
        default { Write-Host $logEntry; break }
    }
}

function Invoke-HeartbeatRequest {
    param(
        [string]$Uri,
        [hashtable]$Headers,
        [string]$Method = "GET",
        [string]$OperationName,
        [int]$TimeoutSec = 30,
        [string]$Body = $null
    )
    
    $attempt = 0
    while ($true) {
        $attempt++
        try {
            Write-HeartbeatLog "Attempt $attempt/$($Script:RetryMaxRetries + 1) for $OperationName" "DEBUG"
            if ($Body) {
                $response = Invoke-RestMethod -Uri $Uri -Headers $Headers -Method $Method -Body $Body -TimeoutSec $TimeoutSec -ContentType "application/json"
            } else {
                $response = Invoke-RestMethod -Uri $Uri -Headers $Headers -Method $Method -TimeoutSec $TimeoutSec
            }
            if ($attempt -gt 1) {
                Write-HeartbeatLog "Succeeded after $attempt attempts: $OperationName" "INFO"
            }
            return $response
        } catch {
            $errorMessage = $_.Exception.Message
            $statusCode = $null
            if ($_.Exception.Response) {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
            
            $isRetryable = $statusCode -ge 500 -or 
                $statusCode -eq 429 -or
                $errorMessage -match "timeout" -or
                $errorMessage -match "connection" -or
                $errorMessage -match "network"
            
            if ($attempt -gt $Script:RetryMaxRetries -or -not $isRetryable) {
                Write-HeartbeatLog "Failed permanently after $attempt attempts: $OperationName - $errorMessage" "ERROR"
                throw $_
            }
            
            $delaySeconds = [Math]::Min($Script:RetryBaseDelay * [Math]::Pow(2, $attempt - 1), $Script:RetryMaxDelay)
            $jitter = Get-Random -Minimum 0.5 -Maximum 1.0
            $delayWithJitter = $delaySeconds * $jitter
            
            Write-HeartbeatLog "Retrying in $([Math]::Round($delayWithJitter, 2))s after $attempt failed attempt(s): $OperationName - $errorMessage" "WARN"
            Start-Sleep -Seconds $delayWithJitter
        }
    }
}