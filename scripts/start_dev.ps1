param(
    [string]$WorkspaceRoot = "",
    [switch]$Fresh,
    [string]$EnvScriptPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$modeContext = Set-RayzaaModeEnvironment -Mode "dev" -WorkspaceRoot $resolvedWorkspaceRoot
$loadedEnvScript = Import-RayzaaLocalEnv -WorkspaceRoot $resolvedWorkspaceRoot -EnvScriptPath $EnvScriptPath
if ($Fresh) {
    & (Join-Path $PSScriptRoot "reset_caches.ps1") -WorkspaceRoot $resolvedWorkspaceRoot -Mode dev
}

Ensure-FrontendDependencies -WebDir $modeContext.Layout.WebDir
Assert-PortAvailable -Port 8000
Assert-PortAvailable -Port 3000

$pythonPath = Resolve-CommandPath -CommandName "python"
$npmPath = Resolve-CommandPath -CommandName "npm.cmd"

Push-Location $modeContext.Layout.WorkspaceRoot
try {
    & $pythonPath ".\scripts\prewarm_model_artifact.py" | Out-Null
} finally {
    Pop-Location
}

$backendOut = Join-Path $modeContext.ModeLogDir "backend.out.log"
$backendErr = Join-Path $modeContext.ModeLogDir "backend.err.log"
$frontendOut = Join-Path $modeContext.ModeLogDir "frontend.out.log"
$frontendErr = Join-Path $modeContext.ModeLogDir "frontend.err.log"

$backend = Start-LoggedProcess `
    -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $modeContext.Layout.ApiDir `
    -StdOutPath $backendOut `
    -StdErrPath $backendErr

$frontend = Start-LoggedProcess `
    -FilePath $npmPath `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $modeContext.Layout.WebDir `
    -StdOutPath $frontendOut `
    -StdErrPath $frontendErr

Write-Host "Rayzaa dev mode started."
Write-Host "  Workspace: $($modeContext.Layout.WorkspaceRoot)"
Write-Host "  Backend: http://127.0.0.1:8000 (PID $($backend.Id))"
Write-Host "  Frontend: http://127.0.0.1:3000 (PID $($frontend.Id))"
Write-Host "  Logs: $($modeContext.ModeLogDir)"
if ($loadedEnvScript) {
    Write-Host "  Integration env: $loadedEnvScript"
}
