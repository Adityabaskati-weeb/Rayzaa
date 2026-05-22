param(
    [string]$WorkspaceRoot = "",
    [ValidateSet("dev", "demo", "benchmark", "all")]
    [string]$Mode = "all",
    [switch]$ResetDatabase,
    [switch]$IncludeArtifacts,
    [switch]$IncludeNodeModules
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$layout = Initialize-RayzaaWorkspace -WorkspaceRoot $resolvedWorkspaceRoot
Assert-RayzaaWorkspaceLayout -Layout $layout

$distDirs = @(
    (Join-Path $layout.WebDir ".next"),
    (Join-Path $layout.WebDir ".next-dev"),
    (Join-Path $layout.WebDir ".next-demo"),
    (Join-Path $layout.WebDir ".next-benchmark")
)

foreach ($dir in $distDirs) {
    Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
}

$modeNames = if ($Mode -eq "all") { @("dev", "demo", "benchmark") } else { @($Mode) }
foreach ($modeName in $modeNames) {
    Remove-Item -LiteralPath (Join-Path $layout.LogsRoot $modeName) -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $layout.TmpRoot $modeName) -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $layout.ReplayRoot $modeName) -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path (Join-Path $layout.LogsRoot $modeName) -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $layout.TmpRoot $modeName) -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $layout.ReplayRoot $modeName) -Force | Out-Null

    if ($ResetDatabase) {
        Remove-Item -LiteralPath (Join-Path $layout.DbDir ("rayzaa_{0}.db" -f $modeName)) -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $layout.DbDir ("rayzaa_{0}.db-journal" -f $modeName)) -Force -ErrorAction SilentlyContinue
    }
}

if ($IncludeArtifacts) {
    Remove-Item -LiteralPath $layout.ArtifactRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $layout.BenchmarkRoot "artifacts") -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $layout.ArtifactRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $layout.BenchmarkRoot "artifacts") -Force | Out-Null
}

if ($IncludeNodeModules) {
    Remove-Item -LiteralPath (Join-Path $layout.WebDir "node_modules") -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Rayzaa caches reset."
Write-Host "  Workspace: $($layout.WorkspaceRoot)"
Write-Host "  Mode: $Mode"
Write-Host "  Dist dirs cleared: $($distDirs.Count)"
