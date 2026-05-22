# Authoritative Workspace

Rayzaa must be built and validated from a clean local path, not from a sync-managed mirror.

Approved authoritative root:

- `C:\Projects\Rayzaa`

The OneDrive copy is mirror-only.

## Layout

```text
C:\Projects\Rayzaa
|-- apps
|-- data
|-- docs
|-- scripts
|-- .runtime
|   |-- artifacts
|   |-- benchmark
|   |-- db
|   |-- demo
|   |-- logs
|   |-- replay
|   `-- tmp
`-- requirements.txt
```

Generated runtime files must stay under `.runtime`.

## Mode Rules

- `dev`
  - `scripts\start_dev.ps1`
  - hot reload
  - `.next-dev`
  - locked artifact validation, no lazy demo retraining
- `demo`
  - `scripts\start_demo.ps1`
  - `.next-demo`
  - deterministic baseline seed
  - demo DB reset
  - live payment before replay
- `benchmark`
  - `scripts\run_benchmark.ps1`
  - no frontend dependency
  - isolated benchmark DB and artifacts
  - the only mode allowed to rebuild the scorer intentionally

## Bootstrap

From the mirror:

```powershell
.\scripts\bootstrap_authoritative_workspace.ps1 -TargetRoot C:\Projects\Rayzaa
```

## Build Safety

- `scripts\check_frontend_build.ps1` performs a bounded production build.
- Frontend output directories are mode-specific: `.next-dev`, `.next-demo`, `.next-benchmark`.
- Frontend watchers ignore `.runtime`, `.artifacts`, benchmark noise, raw data, and local SQLite files.

## Cleanup

Use:

```powershell
.\scripts\reset_caches.ps1 -Mode all -ResetDatabase
```

Use `-IncludeArtifacts` only when intentionally replacing the approved model bundle.
