# Rayzaa Hackathon Architecture

## Objective

Transform a large fraud intelligence architecture into a lean, believable system that a small team can execute in roughly 16 hours.

## System Cut

```text
Synthetic + seeded transaction stream
  -> feature extraction
  -> fraud scorer
  -> graph-risk scorer
  -> profile-drift scorer
  -> fusion policy
  -> decision engine
  -> explanation + analyst workflow
  -> feedback capture
```

## Real Components

- Event simulator with realistic UPI/card-style payloads
- Feature extraction for amount, velocity, location, merchant, device, and profile-change fields
- Base fraud scoring with a lightweight ML model
- Graph-risk scoring with heuristic neighborhood logic
- Drift scoring with rules or a small classifier
- Decision bands: approve, review, block
- SHAP-backed explanation output
- Analyst dashboard and case queue

## Simulated Components

- Voice biometric verification
- Device revalidation confidence if full device telemetry is unavailable
- Adaptive threshold tuning framed as policy controls
- Retraining trigger and feedback loop visuals
- AML/KYC escalation downstream workflow

## Precomputed Components

- Hero fraud-ring scenarios for the graph demo
- Cached SHAP outputs for selected showcase cases if latency is a risk
- Geo clusters and heatmap data
- A small set of account-drift narratives

## Recommended Scoring Design

### 1. Fraud Score

Use one of:

- Gradient boosting model on engineered features
- Isolation Forest for anomaly score
- Optional tiny autoencoder only if time permits

### 2. Graph-Risk Score

Use heuristics instead of a trained GNN:

- shared device count
- shared merchant concentration
- burst connectivity in a short time window
- suspicious neighbor propagation
- ring density score

### 3. Profile-Drift Score

Use rules or a small classifier on:

- dormant to active shift
- sudden amount spike vs user baseline
- location drift
- KYC/profile change markers
- device novelty

### 4. Fusion Policy

Weighted combination of:

- fraud score
- ring-risk score
- drift score
- simulated verification signal

## Decision Policy

- `0-39`: approve
- `40-74`: review
- `75-100`: block or high-risk escalation

Thresholds can be surfaced in the UI as policy controls even if tuning is not learned online.

## Why This Cut Works

This architecture preserves the strongest signals from the original concept:

- strong AI identity
- graph intelligence flavor
- explainability
- analyst workflow
- enterprise demo feel

It removes the slowest, least demo-efficient work:

- multi-model research pipelines
- real-time distributed infra
- production AML systems
- heavy GNN training
- RL policy optimization
