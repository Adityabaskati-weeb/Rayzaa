# Web App

This package should host the analyst-facing fraud operations console.

## Responsibilities

- live transaction stream UI
- fraud graph visualization
- investigation queue
- explanation drawer
- geographic risk view
- threshold and analyst feedback controls

## Design Direction

Avoid generic admin dashboard styling.

Target a modern fintech SOC feel:

- deep neutral background
- sharp signal colors for risk states
- animated graph transitions
- clear event hierarchy
- dense but readable operator layout

## Suggested Views

- `/`: main command center
- `/cases/[id]`: investigation detail
- `/drift`: account drift queue
- `/replay`: scripted demo mode

## Suggested Tech

- Next.js
- Tailwind CSS
- Framer Motion
- Cytoscape.js
- Recharts or Visx only where needed
