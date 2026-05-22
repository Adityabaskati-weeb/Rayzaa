param(
    [string]$WorkspaceRoot = "",
    [int]$BuildTimeoutSeconds = 180,
    [switch]$SkipSeed,
    [string]$EnvScriptPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$modeContext = Set-RayzaaModeEnvironment -Mode "demo" -WorkspaceRoot $resolvedWorkspaceRoot
$loadedEnvScript = Import-RayzaaLocalEnv -WorkspaceRoot $resolvedWorkspaceRoot -EnvScriptPath $EnvScriptPath

$pythonPath = Resolve-CommandPath -CommandName "python"
$npmPath = Resolve-CommandPath -CommandName "npm.cmd"

& (Join-Path $PSScriptRoot "reset_caches.ps1") -WorkspaceRoot $resolvedWorkspaceRoot -Mode demo -ResetDatabase | Out-Null

Push-Location $modeContext.Layout.WorkspaceRoot
try {
    & $pythonPath ".\scripts\prewarm_model_artifact.py" | Out-Null
} finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "check_frontend_build.ps1") -WorkspaceRoot $resolvedWorkspaceRoot -Mode demo -TimeoutSeconds $BuildTimeoutSeconds | Out-Null

Assert-PortAvailable -Port 8000
Assert-PortAvailable -Port 3000

$backendOut = Join-Path $modeContext.ModeLogDir "backend.out.log"
$backendErr = Join-Path $modeContext.ModeLogDir "backend.err.log"
$frontendOut = Join-Path $modeContext.ModeLogDir "frontend.out.log"
$frontendErr = Join-Path $modeContext.ModeLogDir "frontend.err.log"

$backend = Start-LoggedProcess `
    -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $modeContext.Layout.ApiDir `
    -StdOutPath $backendOut `
    -StdErrPath $backendErr

$frontend = Start-LoggedProcess `
    -FilePath $npmPath `
    -ArgumentList @("run", "start") `
    -WorkingDirectory $modeContext.Layout.WebDir `
    -StdOutPath $frontendOut `
    -StdErrPath $frontendErr

Start-Sleep -Seconds 4

if (-not $SkipSeed) {
    $env:RAYZAA_API_BASE = "http://127.0.0.1:8000"
    Push-Location $modeContext.Layout.WorkspaceRoot
    try {
        & $pythonPath ".\scripts\seed_payeasy_demo_baseline.py"
    } finally {
        Pop-Location
    }
}

$warnings = Get-RayzaaIntegrationWarnings

Write-Host "Rayzaa demo mode started."
Write-Host "  Workspace: $($modeContext.Layout.WorkspaceRoot)"
Write-Host "  Backend: http://127.0.0.1:8000 (PID $($backend.Id))"
Write-Host "  Frontend: http://127.0.0.1:3000 (PID $($frontend.Id))"
Write-Host "  Dist dir: $(Join-Path $modeContext.Layout.WebDir $modeContext.DistDir)"
Write-Host "  Logs: $($modeContext.ModeLogDir)"
Write-Host "  Telegram minimum trust state: $env:RAYZAA_TELEGRAM_MIN_TRUST_STATE"
Write-Host "  Demo order: seed baseline -> live payment -> trust update -> queue -> Telegram -> Trust Replay"
if ($loadedEnvScript) {
    Write-Host "  Integration env: $loadedEnvScript"
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings:"
    foreach ($warning in $warnings) {
        Write-Host "  - $warning"
    }
}
