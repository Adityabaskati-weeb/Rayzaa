param(
    [string]$WorkspaceRoot = "",
    [ValidateSet("dev", "demo")]
    [string]$Mode = "demo",
    [string]$EnvScriptPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$modeContext = Set-RayzaaModeEnvironment -Mode $Mode -WorkspaceRoot $resolvedWorkspaceRoot
$loadedEnvScript = Import-RayzaaLocalEnv -WorkspaceRoot $resolvedWorkspaceRoot -EnvScriptPath $EnvScriptPath
$warnings = @(Get-RayzaaIntegrationWarnings)
$envScriptDisplay = if ($loadedEnvScript) { $loadedEnvScript } else { "not loaded" }

function Get-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return [System.Environment]::GetEnvironmentVariable($Name)
}

function Test-PublicHttpsUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $value = Get-EnvValue -Name $Name
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $false
    }

    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -eq "https://replace-me.example.com") {
        return $false
    }
    if (-not $normalized.StartsWith("https://")) {
        return $false
    }
    if ($normalized -match "localhost|127\.0\.0\.1|0\.0\.0\.0") {
        return $false
    }

    return $true
}

function Test-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $value = Get-EnvValue -Name $Name
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $false
    }

    $normalized = $value.Trim().ToLowerInvariant()
    if (
        $normalized -eq "replace_me" -or
        $normalized -eq "rzp_test_replace_me" -or
        $normalized -eq "123456789:replace_me" -or
        $normalized -eq "https://replace-me.example.com" -or
        $normalized -eq "wss://replace-me.example.com/ws/live"
    ) {
        return $false
    }

    return $true
}

function Show-Status {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [bool]$Ready,
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Detail
    )

    $state = if ($Ready) { "READY " } else { "MISSING" }
    Write-Host ("[{0}] {1} - {2}" -f $state, $Label, $Detail)
}

Write-Host "Rayzaa live integration readiness"
Write-Host "  Workspace: $($modeContext.Layout.WorkspaceRoot)"
Write-Host "  Mode: $Mode"
Write-Host "  Env script: $envScriptDisplay"
Write-Host ""

Show-Status -Label "Razorpay key id" -Ready (Test-EnvValue -Name "RAZORPAY_KEY_ID") -Detail "Needed for order creation and checkout"
Show-Status -Label "Razorpay key secret" -Ready (Test-EnvValue -Name "RAZORPAY_KEY_SECRET") -Detail "Needed for order auth and checkout signature verification"
Show-Status -Label "Razorpay webhook secret" -Ready (Test-EnvValue -Name "RAZORPAY_WEBHOOK_SECRET") -Detail "Needed for X-Razorpay-Signature verification"
Show-Status -Label "Telegram bot token" -Ready (Test-EnvValue -Name "TELEGRAM_BOT_TOKEN") -Detail "Needed for sendMessage alert delivery"
Show-Status -Label "Telegram chat id" -Ready (Test-EnvValue -Name "TELEGRAM_CHAT_ID") -Detail "Needed for Telegram destination routing"
Show-Status -Label "Public app URL" -Ready (Test-EnvValue -Name "RAYZAA_PUBLIC_APP_URL") -Detail $(Get-EnvValue -Name "RAYZAA_PUBLIC_APP_URL")
Show-Status -Label "Public API URL" -Ready (Test-PublicHttpsUrl -Name "RAYZAA_PUBLIC_API_URL") -Detail $(Get-EnvValue -Name "RAYZAA_PUBLIC_API_URL")
Show-Status -Label "Backend CORS origin" -Ready (Test-EnvValue -Name "RAYZAA_CORS_ORIGIN") -Detail $(if (Get-EnvValue -Name "RAYZAA_CORS_ORIGIN") { Get-EnvValue -Name "RAYZAA_CORS_ORIGIN" } else { "not set; backend default applies" })
Show-Status -Label "Demo flow lock" -Ready ($env:RAYZAA_DEMO_FLOW_LOCK -eq "1") -Detail "Replay remains locked until one non-seed live payment"

Write-Host ""
Write-Host "Recommended webhook URL:"
Write-Host "  $($env:RAYZAA_PUBLIC_API_URL.TrimEnd('/'))/api/integrations/razorpay/webhook"
Write-Host ""

if ($warnings.Count -gt 0) {
    Write-Host "Warnings:"
    foreach ($warning in $warnings) {
        Write-Host "  - $warning"
    }
    Write-Host ""
}

try {
    $statusResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/integrations/status" -TimeoutSec 5
    Write-Host "Live backend status:"
    Write-Host "  Razorpay configured: $($statusResponse.razorpay.configured)"
    Write-Host "  Razorpay webhook configured: $($statusResponse.razorpay.webhookConfigured)"
    Write-Host "  Razorpay test mode: $($statusResponse.razorpay.testMode)"
    Write-Host "  Telegram configured: $($statusResponse.telegram.configured)"
    Write-Host "  Telegram minimum trust state: $($statusResponse.telegram.minimumTrustState)"
} catch {
    Write-Host "Live backend status: backend not running on http://127.0.0.1:8000"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Copy config\\local.env.ps1.example to config\\local.env.ps1 in the authoritative workspace."
Write-Host "  2. Fill Razorpay test keys, webhook secret, public API URL, and Telegram bot/chat settings."
Write-Host "  3. Create the Razorpay webhook for payment.captured."
Write-Host "  4. Run .\\scripts\\start_demo.ps1 -WorkspaceRoot C:\\Projects\\Rayzaa"
