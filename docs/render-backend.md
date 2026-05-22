# Render Backend Deployment

Rayzaa's hosted backend should run as a single Render web service with one persistent disk.

## Why This Shape

- FastAPI + WebSocket support fits Render directly.
- The current demo uses one backend instance and does not need horizontal scaling.
- SQLite plus a Render disk is the lowest-risk hosted demo path.
- The locked `benchmark_v3` model bundle is prewarmed from the repo and lazy retraining stays disabled.

## Repo Files

- `render.yaml`
- `requirements.txt`
- `scripts/render-start-backend.sh`
- `deploy/artifacts/fraud_model/benchmark_v3/*`

## Required Secrets

Set these in Render before the first live demo:

- `RAYZAA_PUBLIC_APP_URL`
- `RAYZAA_CORS_ORIGIN`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_MESSAGE_THREAD_ID` optional

## Runtime Behavior

At boot the service:

1. mounts persistent runtime storage under `/var/data/rayzaa`
2. exports deterministic runtime paths
3. seeds the approved `benchmark_v3` artifact bundle into runtime storage
4. starts `uvicorn` on the Render-provided port

If the service was created manually without a mounted disk, startup falls back to `/tmp/rayzaa` so the backend can still boot and serve the demo. That fallback is ephemeral, but it is sufficient for the current hosted frontend + backend validation flow.

## Health Check

Use:

- `/health`

## Frontend Wiring After Backend Deploy

After Render gives you the public service URL, set these in Vercel:

- `NEXT_PUBLIC_API_BASE=https://YOUR_RENDER_HOST`
- `NEXT_PUBLIC_WS_URL=wss://YOUR_RENDER_HOST/ws/live`

Then redeploy the Vercel frontend.
