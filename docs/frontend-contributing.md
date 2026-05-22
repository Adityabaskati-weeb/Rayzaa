# Rayzaa Frontend Contribution Guide

## Purpose

The frontend now uses a container-plus-panels architecture so multiple contributors can work in parallel without rewriting the same file.

## Workflow

1. Pick an issue
2. Create a branch from latest main
3. Stay inside one surface unless the PR is an approved extraction/refactor
4. Attach screenshots for static changes
5. Attach a short video for interaction changes
6. Document which backend fields the UI depends on

## Branch Naming

- `codex/frontend/signal-rail-refine`
- `codex/frontend/evidence-lens-phase-c`
- `codex/frontend/replay-controls`

## Commit Naming

- `feat(web): refine escalation queue card hierarchy`
- `fix(web): preserve selected live case during replay updates`
- `refactor(web): extract evidence lens panel`
- `perf(web): reduce graph relayout churn`

## PR Rules

- one PR per surface
- no mega-PRs
- no backend contract changes in frontend-only PRs
- no new dependencies without explicit justification
- no fake data added to make the UI look richer

## Verification Expectations

For each PR, note which of these you checked locally:

- initial load
- websocket live update path
- replay path
- selected case behavior
- empty/loading/error state for touched surface
- responsive behavior for touched surface

## Review Checklist

- does the UI remain truthful to backend semantics?
- does the PR stay inside its issue boundary?
- does it avoid touching unrelated surfaces?
- does it preserve replay/live coexistence?
- are screenshots/video attached?
- are empty states and null-safe cases handled?

## Anti-Patterns

Do not:

- add local risk logic
- hardcode explanation text not backed by payloads
- rename payload fields in components
- build giant conditional trees back into `command-center.jsx`
- add motion that hides state transitions
- use the graph as decorative wallpaper
