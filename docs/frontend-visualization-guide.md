# Frontend Visualization Guide

This guide freezes the Rayzaa command-center visual direction without changing backend semantics.

## Visual Goal

Rayzaa should look like a restrained operational intelligence console:

- enterprise-grade
- forensic
- analyst-centered
- replay-aware
- explainability-first

It should not look like:

- generic SaaS analytics
- neon cyberpunk
- AI-hype theater
- decorative dashboard clutter

## Screenshot-Ready States

Use these states for deck, README, and demo capture.

### 1. Live Payment Proof

- Razorpay test checkout card visible
- one latest live trigger visible
- Telegram card visible
- demo overlay sequence showing live payment complete

### 2. Watch-State Investigation

- active case in `Watch`
- Evidence Lens open on `Case Studio`
- model, graph, drift, and policy sections all visible
- queue showing at least one review item

### 3. Trust Replay Scene

- replay scrubber visible
- active step highlighted
- graph synchronized
- Evidence Lens pinned to replay step
- timeline showing replay marker context

### 4. Escalation Queue Scene

- queue tab active
- at least one escalated item
- one selected queue entry
- clear priority chips and severity differentiation

### 5. Graph Investigation Scene

- graph centered on the focus account
- mixed account/device/merchant/geo nodes visible
- trust-state pill visible
- topology metrics visible

## Contributor-Safe PR Breakdown

### PR 1: Command Shell + Demo Overlay

Scope:

- [apps/web/components/command-center.jsx](../apps/web/components/command-center.jsx)
- [apps/web/app/globals.css](../apps/web/app/globals.css)

Rules:

- no API contract changes
- no trust-state logic changes
- no replay logic changes

### PR 2: Evidence Lens Polish

Scope:

- [apps/web/components/command-center/evidence-lens-panel.jsx](../apps/web/components/command-center/evidence-lens-panel.jsx)
- [apps/web/components/command-center/case-timeline.jsx](../apps/web/components/command-center/case-timeline.jsx)
- [apps/web/app/globals.css](../apps/web/app/globals.css)

Rules:

- keep typed evidence groups intact
- SHAP stays inside `Model Evidence`
- no frontend-generated evidence text

### PR 3: Replay Surface + Choreography

Scope:

- [apps/web/components/command-center/replay-panel.jsx](../apps/web/components/command-center/replay-panel.jsx)
- [apps/web/components/trust-graph.jsx](../apps/web/components/trust-graph.jsx)
- [apps/web/app/globals.css](../apps/web/app/globals.css)

Rules:

- no new replay state ownership
- no replay timeline mutation
- no alternate scoring path

### PR 4: Queue + Signal Rail Scan Speed

Scope:

- [apps/web/components/command-center/queue-panel.jsx](../apps/web/components/command-center/queue-panel.jsx)
- [apps/web/components/command-center/signal-rail-panel.jsx](../apps/web/components/command-center/signal-rail-panel.jsx)
- [apps/web/app/globals.css](../apps/web/app/globals.css)

Rules:

- preserve backend queue order
- do not rerank locally
- do not hide source labels

### PR 5: Responsive Demo Mode

Scope:

- [apps/web/app/globals.css](../apps/web/app/globals.css)
- screenshot verification in authoritative workspace

Rules:

- optimize for 1280px projector layouts
- preserve graph, queue, and Evidence Lens readability
- avoid introducing layout-specific backend assumptions

## Merge Sequence

1. Command shell + overlay
2. Evidence Lens + timeline
3. Replay + graph
4. Queue + Signal Rail
5. Responsive tuning + screenshot verification

## Screenshot Checklist

- authoritative workspace only: `C:\Projects\Rayzaa`
- use demo mode or a bounded local startup
- avoid empty queue screenshots unless illustrating fallback state
- capture one live-trust scene and one replay scene
- capture with the browser window at roughly `1280px` width

## Final Feel Audit

The frontend is acceptable when:

- the queue reads like triage, not a task list
- the timeline reads like chronology, not a feed
- replay reads like investigation control, not video playback
- Evidence Lens reads like disciplined evidence, not “AI insights”
- the graph reads like topology, not decorative complexity
