param(
    [string]$WorkspaceRoot = "",
    [ValidateSet("dev", "demo", "benchmark")]
    [string]$Mode = "demo",
    [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$modeContext = Set-RayzaaModeEnvironment -Mode $Mode -WorkspaceRoot $resolvedWorkspaceRoot
Ensure-FrontendDependencies -WebDir $modeContext.Layout.WebDir
$npmPath = Resolve-CommandPath -CommandName "npm.cmd"

$distPath = Join-Path $modeContext.Layout.WebDir $modeContext.DistDir
Remove-Item -LiteralPath $distPath -Recurse -Force -ErrorAction SilentlyContinue

$buildOut = Join-Path $modeContext.ModeLogDir "frontend-build.out.log"
$buildErr = Join-Path $modeContext.ModeLogDir "frontend-build.err.log"

Invoke-BoundedProcess `
    -FilePath $npmPath `
    -ArgumentList @("run", "build") `
    -WorkingDirectory $modeContext.Layout.WebDir `
    -StdOutPath $buildOut `
    -StdErrPath $buildErr `
    -TimeoutSeconds $TimeoutSeconds | Out-Null

Write-Host "Frontend build completed successfully."
Write-Host "  Mode: $Mode"
Write-Host "  Dist dir: $distPath"
Write-Host "  Logs: $($modeContext.ModeLogDir)"
