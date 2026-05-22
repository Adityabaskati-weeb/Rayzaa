# Vercel Frontend Deployment

Deploy only the Rayzaa frontend from:

- `apps/web`

Use the authoritative local workspace for validation:

- `C:\Projects\Rayzaa`

## Recommended Project Settings

In Vercel:

1. Import the GitHub repository.
2. Set the project `Root Directory` to:

```text
apps/web
```

3. Framework preset:

```text
Next.js
```

4. Build command:

```text
npm run build
```

5. Output directory:

```text
.next
```

## Required Environment Variables

Add these in Vercel Project Settings:

```text
NEXT_PUBLIC_API_BASE=https://YOUR_PUBLIC_BACKEND_HOST
NEXT_PUBLIC_WS_URL=wss://YOUR_PUBLIC_BACKEND_HOST/ws/live
```

Examples:

```text
NEXT_PUBLIC_API_BASE=https://rayzaa-api.onrender.com
NEXT_PUBLIC_WS_URL=wss://rayzaa-api.onrender.com/ws/live
```

Do not use:

- `http://127.0.0.1:8000`
- `ws://127.0.0.1:8000/ws/live`

outside local development.

## Backend Requirements

The hosted frontend depends on:

- `GET /api/state`
- `GET /api/cases/:id`
- `POST /api/integrations/razorpay/orders`
- `POST /api/integrations/razorpay/checkout/verify`
- `WebSocket /ws/live`

Your backend host must also allow the frontend origin through:

- `RAYZAA_CORS_ORIGIN`

## What Happens If You Forget Env Vars

Rayzaa now shows a visible deployment-configuration warning instead of silently trying localhost in production.

## Local Validation Before Vercel

```powershell
cd C:\Projects\Rayzaa
.\scripts\check_frontend_build.ps1 -WorkspaceRoot C:\Projects\Rayzaa -Mode demo
```

## Recommended Deployment Split

- frontend: Vercel
- backend: Render / Railway / Fly

This keeps the Next.js deployment simple while leaving WebSocket and webhook handling on the backend host.
