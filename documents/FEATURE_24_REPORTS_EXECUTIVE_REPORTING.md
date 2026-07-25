# Feature 24 — Reports & Executive Reporting

## Overview
Feature 24 provides workspace-scoped executive and operational reporting across audits, datasets, issues, quality rules, contracts, schema drift, remediation, alerts, and scheduled monitoring.

## Functional areas
- Executive summary metrics and reliability trends
- Dataset reliability ranking and score distribution evidence
- Issue severity, category, affected-column, and score-versus-issue charts
- Rule pass-rate trends and failed-rule reporting
- Contract, schema-drift, remediation, audit, and alert report modes
- Saved report records and recurring report configurations
- PDF and CSV exports
- Date-range and dataset filters
- Workspace isolation and authenticated access

## Charts
Chart.js powers reliability trend, severity composition, dataset ranking, rule pass rate, issue categories, remediation impact, affected columns, and score-versus-issue scatter analysis.

## Governance
Reports are generated only from data available in the active workspace. Saved reports and schedules are scoped to the current workspace and authenticated user context.

## Future foundations
Production delivery can extend report schedules with email delivery, object storage, branded PDF templates, and a background report worker.
