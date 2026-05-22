param(
    [string]$WorkspaceRoot = "",
    [string]$EnvScriptPath = "",
    [switch]$ShowRaw
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$null = Set-RayzaaModeEnvironment -Mode "demo" -WorkspaceRoot $resolvedWorkspaceRoot
$loadedEnvScript = Import-RayzaaLocalEnv -WorkspaceRoot $resolvedWorkspaceRoot -EnvScriptPath $EnvScriptPath

$botToken = [System.Environment]::GetEnvironmentVariable("TELEGRAM_BOT_TOKEN")
if ([string]::IsNullOrWhiteSpace($botToken) -or $botToken -eq "123456789:replace_me") {
    throw "TELEGRAM_BOT_TOKEN is not configured. Fill config\local.env.ps1 first."
}

$url = "https://api.telegram.org/bot$botToken/getUpdates"
$response = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 15

Write-Host "Telegram chat lookup"
Write-Host "  Env script: $(if ($loadedEnvScript) { $loadedEnvScript } else { 'not loaded' })"
Write-Host ""

if ($ShowRaw) {
    $response | ConvertTo-Json -Depth 8
    return
}

if (-not $response.ok -or -not $response.result -or $response.result.Count -eq 0) {
    Write-Host "No Telegram updates found yet."
    Write-Host "Next:"
    Write-Host "  1. Open a chat with your bot or add it to the target group."
    Write-Host "  2. Send one message manually."
    Write-Host "  3. Re-run this script."
    return
}

$rows = foreach ($item in $response.result) {
    $message = $item.message
    if (-not $message) {
        continue
    }

    [pscustomobject]@{
        UpdateId        = $item.update_id
        ChatId          = $message.chat.id
        ChatType        = $message.chat.type
        ChatTitle       = $message.chat.title
        ChatUsername    = $message.chat.username
        MessageThreadId = $message.message_thread_id
        Sender          = $message.from.username
        Text            = $message.text
    }
}

if (-not $rows) {
    Write-Host "Updates exist, but none contain a plain message payload yet."
    Write-Host "Re-run with -ShowRaw if you need the full payload."
    return
}

$rows | Sort-Object UpdateId -Descending | Format-Table -AutoSize

Write-Host ""
Write-Host "Use:"
Write-Host "  TELEGRAM_CHAT_ID = the ChatId value you want"
Write-Host "  TELEGRAM_MESSAGE_THREAD_ID = the MessageThreadId value only if you are using Telegram forum topics"
