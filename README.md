# Rayzaa

Rayzaa is a hackathon-focused AI fraud intelligence command center designed to feel like a production-inspired fintech risk platform without pretending to implement every research-grade component in one sprint.

## What We Are Building

A believable 16-hour MVP that combines:

- live transaction monitoring
- fraud anomaly scoring
- graph-based ring-risk detection
- account drift detection
- explainable analyst reasoning
- adaptive decisioning
- analyst review workflow

## What We Are Not Building in the Hackathon Sprint

These modules may be represented in the demo, but they should not consume core build time:

- full GNN training pipelines
- RL threshold optimization
- real voice biometrics
- production AML/KYC integrations
- continuous retraining infrastructure
- large-scale distributed streaming systems

## Product Shape

The strongest version of Rayzaa is a fraud operations console with one real scoring path and several clearly framed supporting layers:

1. A transaction event stream enters the system.
2. Features are computed for anomaly, graph, and drift signals.
3. A lightweight scoring stack assigns fraud, ring, and profile-drift risk.
4. A decision engine classifies the event into approve, review, or block.
5. Explainability and analyst tooling turn a score into an investigation workflow.

## Recommended Hackathon Stack

- Frontend: Next.js, Tailwind CSS, Framer Motion
- Backend: FastAPI with WebSocket streaming
- ML: scikit-learn, SHAP, optional small PyTorch autoencoder
- Graph: NetworkX for scoring, Cytoscape.js for visualization
- Demo data: IBM AML-inspired seed data plus synthetic UPI-style events

## Repo Layout

```text
Rayzaa/
  apps/
    api/                # FastAPI service, event simulator, scoring APIs
    web/                # Next.js analyst dashboard
  services/
    ml/                 # Fraud, graph, drift, and explanation logic
  data/
    raw/                # Downloaded or source datasets (not committed if large)
    processed/          # Cached feature tables and demo artifacts
    synthetic/          # Generated demo scenarios and fraud rings
  docs/
    architecture.md     # Lean architecture for the hackathon cut
    mvp-scope.md        # Must/should/fake/post-hackathon breakdown
    demo-flow.md        # Demo script and operator sequence
  schemas/
    transaction-event.schema.json
    case-decision.schema.json
```

## Build Priority

1. Live transaction feed with seeded suspicious cases
2. Core scoring pipeline
3. Graph-risk visualization
4. Explanation panel and analyst brief
5. Decision workflow and review actions
6. Polish, motion, and demo choreography

## Guiding Principle

Do not build every box from the architecture diagram.

Build the minimum number of real systems required for judges to believe the rest of the story.
