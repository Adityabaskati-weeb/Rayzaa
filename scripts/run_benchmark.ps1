param(
    [string]$WorkspaceRoot = "",
    [int]$TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$helperPath = Join-Path $PSScriptRoot "lib\rayzaa-workspace.ps1"
. $helperPath

$resolvedWorkspaceRoot = if ($WorkspaceRoot) { $WorkspaceRoot } else { Get-RayzaaRepoRoot }
$modeContext = Set-RayzaaModeEnvironment -Mode "benchmark" -WorkspaceRoot $resolvedWorkspaceRoot
$pythonPath = Resolve-CommandPath -CommandName "python"
$benchmarkOut = Join-Path $modeContext.ModeLogDir "benchmark.out.log"
$benchmarkErr = Join-Path $modeContext.ModeLogDir "benchmark.err.log"

Invoke-BoundedProcess `
    -FilePath $pythonPath `
    -ArgumentList @(".\\scripts\\prepare_fraud_model.py") `
    -WorkingDirectory $modeContext.Layout.WorkspaceRoot `
    -StdOutPath $benchmarkOut `
    -StdErrPath $benchmarkErr `
    -TimeoutSeconds $TimeoutSeconds | Out-Null

Write-Host "Rayzaa benchmark mode completed."
Write-Host "  Workspace: $($modeContext.Layout.WorkspaceRoot)"
Write-Host "  Artifact dir: $($modeContext.ArtifactDir)"
Write-Host "  Logs: $($modeContext.ModeLogDir)"
