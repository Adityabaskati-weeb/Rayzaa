# Rayzaa Final Demo Runbook

## Authoritative Workspace

Use only:

`C:\Projects\Rayzaa`

Do not run builds, replay, or demo startup from the OneDrive mirror.

## Locked Demo Order

1. Seed benign baseline
2. Complete one live payment
3. Show trust-state transition
4. Show queue update
5. Show Telegram status
6. Open Trust Replay

Baseline seed traffic does not unlock replay.

## Local Demo Startup

Before startup, copy `config\local.env.ps1.example` to `config\local.env.ps1` in the authoritative workspace and fill the real integration values.

```powershell
cd C:\Projects\Rayzaa
.\scripts\check_live_integrations.ps1 -WorkspaceRoot C:\Projects\Rayzaa -Mode demo
.\scripts\reset_caches.ps1 -WorkspaceRoot C:\Projects\Rayzaa -Mode demo -ResetDatabase
.\scripts\start_demo.ps1 -WorkspaceRoot C:\Projects\Rayzaa
```

## Local Validation Checks

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/state | Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:3000 | Select-Object -ExpandProperty StatusCode
```

Expected before the judge payment:

- baseline seed cases visible
- `livePaymentSeen: false`
- replay start returns `409`

Expected after one live payment:

- live case becomes focus
- queue shows the live case if it moves to review or escalation
- replay start returns `200`
- replay completion restores live focus while keeping replay steps available

## Deployment Recommendation

Primary recommendation:

- frontend: Render web service or Vercel
- backend: Render web service
- database: managed Postgres

Safest one-vendor hackathon stack:

- Render frontend + Render backend + managed Postgres

Best split stack if frontend polish matters more than single-vendor simplicity:

- Vercel frontend + Render backend + managed Postgres

## Required Environment Variables

Backend:

- `DATABASE_URL`
- `RAYZAA_CORS_ORIGIN`
- `RAYZAA_PUBLIC_APP_URL`
- `RAYZAA_PUBLIC_API_URL`
- `RAYZAA_MODEL_MODE=benchmark`
- `RAYZAA_LOCKED_MODEL_BUNDLE=benchmark_v3`
- `RAYZAA_ALLOW_ARTIFACT_AUTOTRAIN=0`
- `RAYZAA_ENFORCE_ARTIFACT_MANIFEST=1`
- `RAYZAA_ARTIFACT_MANIFEST`
- `RAYZAA_APPROVED_ARTIFACT_SOURCE`
- `RAYZAA_DEMO_FLOW_LOCK=1` for demo mode
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_MESSAGE_THREAD_ID` optional
- `RAYZAA_TELEGRAM_MIN_TRUST_STATE`

Frontend:

- `NEXT_PUBLIC_API_BASE`
- `NEXT_PUBLIC_WS_URL`

## Artifact Rule

The locked `benchmark_v3` model bundle must exist before startup.

Do not allow lazy retraining in demo or deployed environments.

Package the approved bundle into the deployment artifact or stage it in mounted storage before the backend boots.

## Presenter Guidance

- Prefer Razorpay Test Mode over real money.
- Use a visibly abnormal payment amount near the configured risky preset.
- Do not open replay before the live payment lands.
- End the walkthrough on Evidence Lens or Queue, not on the checkout form.
