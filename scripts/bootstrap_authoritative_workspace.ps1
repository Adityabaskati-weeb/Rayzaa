param(
    [string]$SourceRoot = "",
    [string]$TargetRoot = "C:\Projects\Rayzaa",
    [switch]$InstallFrontendDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedSourceRoot = if ($SourceRoot) { $SourceRoot } else { Get-RayzaaRepoRoot }
$source = [System.IO.Path]::GetFullPath($resolvedSourceRoot)
$target = [System.IO.Path]::GetFullPath($TargetRoot)

Assert-NonOneDrivePath -Path $target
if (-not (Test-Path $source)) {
    throw "Source workspace not found: $source"
}

New-Item -ItemType Directory -Path $target -Force | Out-Null

$dirExcludes = @(
    ".git",
    "node_modules",
    ".next",
    ".next-dev",
    ".next-demo",
    ".next-benchmark",
    ".runtime",
    ".runtime_logs",
    ".artifacts",
    ".bench_artifacts",
    ".bench_artifacts2"
)
$fileExcludes = @(
    "rayzaa.db",
    "rayzaa.db-journal"
)
$targetLocalEnv = Join-Path $target "config\local.env.ps1"
$preservedLocalEnv = Join-Path $env:TEMP "rayzaa-local-env.ps1"

if (Test-Path $targetLocalEnv) {
    Copy-Item -LiteralPath $targetLocalEnv -Destination $preservedLocalEnv -Force
}

Write-Host "Syncing Rayzaa source to $target"
& robocopy $source $target /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD $dirExcludes /XF $fileExcludes | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -gt 7) {
    throw "Robocopy failed with exit code $robocopyExit"
}

$layout = Initialize-RayzaaWorkspace -WorkspaceRoot $target
Assert-RayzaaWorkspaceLayout -Layout $layout

if (Test-Path $preservedLocalEnv) {
    New-Item -ItemType Directory -Path (Join-Path $target "config") -Force | Out-Null
    Copy-Item -LiteralPath $preservedLocalEnv -Destination $targetLocalEnv -Force
    Remove-Item -LiteralPath $preservedLocalEnv -Force -ErrorAction SilentlyContinue
}

if ($InstallFrontendDeps) {
    Ensure-FrontendDependencies -WebDir $layout.WebDir
}

Write-Host "Authoritative workspace ready:"
Write-Host "  Root: $($layout.WorkspaceRoot)"
Write-Host "  Runtime: $($layout.RuntimeRoot)"
Write-Host "  Logs: $($layout.LogsRoot)"
Write-Host "  Web: $($layout.WebDir)"
Write-Host "  API: $($layout.ApiDir)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Run scripts\\prewarm_model_artifact.py from the authoritative workspace if the approved bundle is not already present."
Write-Host "  2. Run scripts\\check_frontend_build.ps1 from the authoritative workspace."
Write-Host "  3. Run scripts\\start_demo.ps1 or scripts\\start_dev.ps1 from the authoritative workspace."
