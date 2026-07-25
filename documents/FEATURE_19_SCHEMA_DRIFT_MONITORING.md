# Feature 19 — Schema Drift Monitoring

## Overview
Schema Drift Monitoring detects structural and statistical changes between consecutive audit-backed dataset versions. It gives teams a workspace-scoped view of drift severity, impact, history, and affected columns.

## Core capability
- Detects added and removed columns.
- Detects inferred data-type changes.
- Detects material missing-rate and cardinality shifts.
- Classifies drift as high, medium, or low severity.
- Scores impact from 1–100.
- Tracks new, persistent, and resolved drift events.

## Workspace
The full-page workspace includes KPI cards, Chart.js trend and distribution charts, filters, a paginated event registry, detailed event evidence, CSV export, and navigation to Dataset Versions or the candidate audit.

## APIs
- `GET /schema-drift`
- `GET /schema-drift/export`
- `GET /schema-drift/{event_id}`

All endpoints enforce active-workspace isolation.

## Future foundations
The event model is ready for contract-aware classifications, scheduled monitoring, notification thresholds, acknowledged events, and richer distribution-drift tests.
