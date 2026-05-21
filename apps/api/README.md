# API Service

This package should host the backend orchestration layer for the demo.

## Responsibilities

- event simulator and seeded scenario playback
- feature extraction endpoints
- fraud scoring API
- graph-risk and drift scoring API
- WebSocket stream for the frontend
- decision engine and case state updates

## Suggested Endpoints

- `GET /health`
- `GET /stream/scenario/{name}`
- `POST /score/transaction`
- `POST /score/case`
- `GET /cases`
- `POST /cases/{id}/action`
- `GET /metrics/overview`

## Suggested Runtime

- FastAPI
- Pydantic models from `schemas/`
- WebSockets for event push
- lightweight in-memory state for hackathon speed

## Important Constraint

Keep the API thin. Complex model logic should live under `services/ml`.
