Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RayzaaRepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
}

function Import-RayzaaLocalEnv {
    param(
        [string]$WorkspaceRoot = (Get-RayzaaRepoRoot),
        [string]$EnvScriptPath = ""
    )

    $resolvedWorkspaceRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot)
    $candidate = if ($EnvScriptPath) {
        if ([System.IO.Path]::IsPathRooted($EnvScriptPath)) {
            $EnvScriptPath
        } else {
            Join-Path $resolvedWorkspaceRoot $EnvScriptPath
        }
    } else {
        Join-Path $resolvedWorkspaceRoot "config\local.env.ps1"
    }

    $resolvedCandidate = [System.IO.Path]::GetFullPath($candidate)
    if (-not (Test-Path $resolvedCandidate)) {
        return $null
    }

    . $resolvedCandidate
    return $resolvedCandidate
}

function Assert-NonOneDrivePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ($Path -match "(?i)onedrive|dropbox|google drive|icloud") {
        throw "Path '$Path' is under a sync-managed workspace. Use a short non-OneDrive path such as C:\Projects\Rayzaa."
    }
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    return [System.IO.Path]::GetFullPath($Path)
}

function Resolve-CommandPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName
    )

    $command = Get-Command $CommandName -ErrorAction Stop
    return $command.Source
}

function Get-RayzaaWorkspaceLayout {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    $root = [System.IO.Path]::GetFullPath($WorkspaceRoot)
    $runtimeRoot = Join-Path $root ".runtime"

    return [pscustomobject]@{
        WorkspaceRoot = $root
        RuntimeRoot   = $runtimeRoot
        DbDir         = Join-Path $runtimeRoot "db"
        ReplayRoot    = Join-Path $runtimeRoot "replay"
        LogsRoot      = Join-Path $runtimeRoot "logs"
        TmpRoot       = Join-Path $runtimeRoot "tmp"
        BenchmarkRoot = Join-Path $runtimeRoot "benchmark"
        ArtifactRoot  = Join-Path $runtimeRoot "artifacts"
        WebDir        = Join-Path $root "apps\web"
        ApiDir        = Join-Path $root "apps\api"
    }
}

function Initialize-RayzaaWorkspace {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    Assert-NonOneDrivePath -Path $WorkspaceRoot
    $layout = Get-RayzaaWorkspaceLayout -WorkspaceRoot $WorkspaceRoot

    @(
        $layout.RuntimeRoot,
        $layout.DbDir,
        $layout.ReplayRoot,
        $layout.LogsRoot,
        $layout.TmpRoot,
        $layout.BenchmarkRoot,
        $layout.ArtifactRoot
    ) | ForEach-Object {
        Ensure-Directory -Path $_ | Out-Null
    }

    return $layout
}

function Assert-RayzaaWorkspaceLayout {
    param(
        [Parameter(Mandatory = $true)]
        $Layout
    )

    $requiredPaths = @(
        (Join-Path $Layout.ApiDir "main.py"),
        (Join-Path $Layout.WebDir "package.json"),
        (Join-Path $Layout.WorkspaceRoot "requirements.txt")
    )

    foreach ($path in $requiredPaths) {
        if (-not (Test-Path $path)) {
            throw "Required workspace path missing: $path"
        }
    }
}

function Set-RayzaaModeEnvironment {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("dev", "demo", "benchmark")]
        [string]$Mode,
        [string]$WorkspaceRoot = (Get-RayzaaRepoRoot)
    )

    $layout = Initialize-RayzaaWorkspace -WorkspaceRoot $WorkspaceRoot
    Assert-RayzaaWorkspaceLayout -Layout $layout

    $modeRuntimeDir = Ensure-Directory -Path (Join-Path $layout.RuntimeRoot $Mode)
    $modeReplayDir = Ensure-Directory -Path (Join-Path $layout.ReplayRoot $Mode)
    $modeLogDir = Ensure-Directory -Path (Join-Path $layout.LogsRoot $Mode)
    $modeTmpDir = Ensure-Directory -Path (Join-Path $layout.TmpRoot $Mode)
    $modeBenchmarkDir = Ensure-Directory -Path (Join-Path $layout.BenchmarkRoot $Mode)
    $dbPath = [System.IO.Path]::GetFullPath((Join-Path $layout.DbDir ("rayzaa_{0}.db" -f $Mode)))
    $artifactDir = if ($Mode -eq "benchmark") {
        Ensure-Directory -Path (Join-Path $modeBenchmarkDir "artifacts")
    } else {
        Ensure-Directory -Path $layout.ArtifactRoot
    }

    $distDir = switch ($Mode) {
        "dev" { ".next-dev" }
        "demo" { ".next-demo" }
        default { ".next-benchmark" }
    }

    $env:DATABASE_URL = "sqlite:///$($dbPath.Replace('\', '/'))"
    $env:RAYZAA_RUNTIME_DIR = $modeRuntimeDir
    $env:RAYZAA_REPLAY_DIR = $modeReplayDir
    $env:RAYZAA_LOG_DIR = $modeLogDir
    $env:RAYZAA_BENCHMARK_DIR = $modeBenchmarkDir
    $env:RAYZAA_TMP_DIR = $modeTmpDir
    $env:RAYZAA_ARTIFACT_DIR = $artifactDir
    $env:RAYZAA_MODEL_MODE = "benchmark"
    $env:RAYZAA_LOCKED_MODEL_BUNDLE = "benchmark_v3"
    $env:RAYZAA_ARTIFACT_MANIFEST = [System.IO.Path]::GetFullPath((Join-Path $layout.WorkspaceRoot "docs\approved_model_artifact.json"))
    $env:RAYZAA_APPROVED_ARTIFACT_SOURCE = [System.IO.Path]::GetFullPath((Join-Path $layout.WorkspaceRoot ".runtime\benchmark\benchmark\artifacts\fraud_model\benchmark_v3"))
    $env:RAYZAA_ALLOW_ARTIFACT_AUTOTRAIN = if ($Mode -eq "benchmark") { "1" } else { "0" }
    $env:RAYZAA_ENFORCE_ARTIFACT_MANIFEST = if ($Mode -eq "benchmark") { "0" } else { "1" }
    $env:RAYZAA_DEMO_FLOW_LOCK = if ($Mode -eq "demo") { "1" } else { "0" }
    $env:RAYZAA_NEXT_DIST_DIR = $distDir
    $env:NEXT_PUBLIC_API_BASE = "http://127.0.0.1:8000"
    $env:NEXT_PUBLIC_WS_URL = "ws://127.0.0.1:8000/ws/live"
    $env:RAYZAA_PUBLIC_APP_URL = "http://127.0.0.1:3000"
    $env:RAYZAA_PUBLIC_API_URL = "http://127.0.0.1:8000"

    if ($Mode -eq "demo" -and -not $env:RAYZAA_TELEGRAM_MIN_TRUST_STATE) {
        $env:RAYZAA_TELEGRAM_MIN_TRUST_STATE = "Watch"
    }

    return [pscustomobject]@{
        Mode           = $Mode
        Layout         = $layout
        DbPath         = $dbPath
        ArtifactDir    = $artifactDir
        ModeRuntimeDir = $modeRuntimeDir
        ModeReplayDir  = $modeReplayDir
        ModeLogDir     = $modeLogDir
        ModeTmpDir     = $modeTmpDir
        DistDir        = $distDir
    }
}

function Ensure-FrontendDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WebDir
    )

    if (Test-Path (Join-Path $WebDir "node_modules")) {
        return
    }

    $npmPath = Resolve-CommandPath -CommandName "npm.cmd"
    Push-Location $WebDir
    try {
        & $npmPath ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed in $WebDir"
        }
    } finally {
        Pop-Location
    }
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port $Port is already in use. Stop the existing service before launching Rayzaa."
    }
}

function Start-LoggedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$StdOutPath,
        [Parameter(Mandatory = $true)]
        [string]$StdErrPath
    )

    Remove-Item $StdOutPath, $StdErrPath -Force -ErrorAction SilentlyContinue
    return Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError $StdErrPath `
        -PassThru `
        -WindowStyle Hidden
}

function Invoke-BoundedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$StdOutPath,
        [Parameter(Mandatory = $true)]
        [string]$StdErrPath,
        [int]$TimeoutSeconds = 180
    )

    $quotedArguments = $ArgumentList | ForEach-Object {
        if ($_ -match "\s") {
            '"' + $_ + '"'
        } else {
            $_
        }
    }

    Remove-Item $StdOutPath, $StdErrPath -Force -ErrorAction SilentlyContinue

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($quotedArguments -join " ")
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $null = $process.Start()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill()
        throw "Process '$FilePath $($ArgumentList -join ' ')' exceeded the ${TimeoutSeconds}s timeout. Check $StdOutPath and $StdErrPath."
    }

    $process.WaitForExit()
    [System.IO.File]::WriteAllText($StdOutPath, $stdoutTask.Result)
    [System.IO.File]::WriteAllText($StdErrPath, $stderrTask.Result)

    if ($process.ExitCode -ne 0) {
        throw "Process '$FilePath $($ArgumentList -join ' ')' failed with exit code $($process.ExitCode). Check $StdOutPath and $StdErrPath."
    }

    return $process
}

function Get-RayzaaIntegrationWarnings {
    $warnings = [System.Collections.Generic.List[string]]::new()

    if (-not $env:RAZORPAY_KEY_ID -or -not $env:RAZORPAY_KEY_SECRET -or -not $env:RAZORPAY_WEBHOOK_SECRET) {
        $warnings.Add("Razorpay test credentials are incomplete. Demo mode will need deterministic replay fallback instead of live checkout.")
    }
    if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
        $warnings.Add("Telegram is not configured. Alert fallback will remain visible in the UI and timeline.")
    }
    if ($env:RAZORPAY_KEY_ID -and -not ($env:RAZORPAY_KEY_ID -like "rzp_test_*")) {
        $warnings.Add("Razorpay is not using test-mode credentials. Prefer Test Mode for hackathon demo reliability.")
    }
    if ($env:RAZORPAY_WEBHOOK_SECRET -and -not $env:RAYZAA_PUBLIC_API_URL.StartsWith("https://")) {
        $warnings.Add("RAYZAA_PUBLIC_API_URL is not HTTPS. Razorpay webhooks require a public HTTPS endpoint.")
    }

    return $warnings
}
