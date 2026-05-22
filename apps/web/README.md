# Rayzaa Web

This package now contains the current Rayzaa frontend implementation.

## Product Split

- `/` and `/payeasy`: customer-facing PayEasy checkout dashboard
- `/rayzaa`: analyst-facing Rayzaa trust operations command center

## Current Frontend Surfaces

- Signal Rail
- Evidence Lens
- Trust Replay
- Trust Memory Graph
- Queue Panel
- Case Timeline
- PayEasy live payment proof

## Runtime Requirements

Local development can fall back to:

- `http://127.0.0.1:8000`
- `ws://127.0.0.1:8000/ws/live`

Hosted deployments must set:

- `NEXT_PUBLIC_API_BASE`
- `NEXT_PUBLIC_WS_URL`

See:

- `apps/web/.env.example`
- `docs/vercel-frontend.md`

## Deployment Intent

This package is designed to deploy independently as a Next.js frontend, with the backend hosted separately for API and WebSocket traffic.
