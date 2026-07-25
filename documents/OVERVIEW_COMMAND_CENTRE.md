# Overview Command Centre

## Overview
The Overview page is the high-level operational command centre for the active workspace. It replaces the previous audit-focused dashboard with a concise platform-wide summary.

## Coverage
- Reliability score and current risk posture
- Registered datasets and domains
- Active issues by severity and lifecycle
- Failed quality rules and execution failure rate
- Contract violations and schema drift alerts
- Open governed Action Points used as remediation work
- Recent alerts and platform activity
- Upcoming scheduled audits
- Platform totals for audits, rules, contracts, connectors, reports, and users

## User Experience
The page uses one compact issue-distribution visual and prioritizes information cards, operational lists, and direct actions over multiple charts. The welcome ribbon provides immediate access to audits, critical alerts, and Reliability Copilot.

## Backend
`GET /reports/overview` returns workspace-scoped metrics, lifecycle summaries, activity, alerts, schedules, health information, and platform totals.

## Governance
All results are restricted to the active workspace. Quick actions route users into existing governed workflows rather than modifying data directly.
