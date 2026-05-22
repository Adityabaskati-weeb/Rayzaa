param(
    [string]$WorkspaceRoot = "",
    [string]$EnvScriptPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$null = Set-RayzaaModeEnvironment -Mode "demo" -WorkspaceRoot $resolvedWorkspaceRoot
$loadedEnvScript = Import-RayzaaLocalEnv -WorkspaceRoot $resolvedWorkspaceRoot -EnvScriptPath $EnvScriptPath

function Test-ConfiguredValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    $normalized = $Value.Trim().ToLowerInvariant()
    return -not (
        $normalized -eq "replace_me" -or
        $normalized -eq "rzp_test_replace_me" -or
        $normalized -eq "https://replace-me.example.com"
    )
}

$publicApiUrl = [System.Environment]::GetEnvironmentVariable("RAYZAA_PUBLIC_API_URL")
$keyId = [System.Environment]::GetEnvironmentVariable("RAZORPAY_KEY_ID")
$keySecret = [System.Environment]::GetEnvironmentVariable("RAZORPAY_KEY_SECRET")
$webhookSecret = [System.Environment]::GetEnvironmentVariable("RAZORPAY_WEBHOOK_SECRET")
$webhookEvent = [System.Environment]::GetEnvironmentVariable("RAYZAA_RAZORPAY_WEBHOOK_EVENT")
if ([string]::IsNullOrWhiteSpace($webhookEvent)) {
    $webhookEvent = "payment.captured"
}

$webhookUrl = if ([string]::IsNullOrWhiteSpace($publicApiUrl)) {
    "set RAYZAA_PUBLIC_API_URL first"
} else {
    ($publicApiUrl.TrimEnd("/") + "/api/integrations/razorpay/webhook")
}

Write-Host "Razorpay dashboard values for Rayzaa"
Write-Host "  Env script: $(if ($loadedEnvScript) { $loadedEnvScript } else { 'not loaded' })"
Write-Host ""
Write-Host "Use Test Mode in Razorpay."
Write-Host ""
Write-Host "Webhook URL:"
Write-Host "  $webhookUrl"
Write-Host ""
Write-Host "Subscribe to event:"
Write-Host "  $webhookEvent"
Write-Host ""
Write-Host "Webhook secret:"
if (-not (Test-ConfiguredValue -Value $webhookSecret)) {
    Write-Host "  missing or still placeholder in local env"
} else {
    Write-Host "  configured in local env"
}
Write-Host ""
Write-Host "Razorpay credentials:"
Write-Host "  Key ID configured: $(Test-ConfiguredValue -Value $keyId)"
Write-Host "  Key Secret configured: $(Test-ConfiguredValue -Value $keySecret)"
Write-Host ""
Write-Host "Important:"
Write-Host "  - Use a public HTTPS backend URL, not localhost."
Write-Host "  - Keep webhook event as payment.captured unless you change the Rayzaa backend filter."
Write-Host "  - The checkout callback is not the source of truth. The webhook is."
