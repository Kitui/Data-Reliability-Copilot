# Feature 18 — Dataset Versioning and Audit Comparison

## Overview
Feature 18 adds audit-backed dataset version history and version-aware reliability comparison. Each completed audit for a registered dataset is treated as an immutable snapshot within the active workspace.

## Core capability
- Ordered dataset versions derived from completed audits
- Version metadata: timestamp, score, risk, rows, columns, issues, source file, and audit reference
- Baseline-to-candidate comparison
- Score, row-count, column-count, and issue-count deltas
- Added, removed, and inferred-type schema changes
- New, resolved, and persistent issue classification
- Improved and worsened column completeness indicators

## User experience
A full-page Dataset Versions workspace provides dataset selection, version selectors, lineage history, comparison metrics, schema changes, issue movement, and direct navigation to the selected audit.

## APIs
- `GET /datasets/{dataset_id}/versions`
- `GET /datasets/{dataset_id}/versions/compare`

Both endpoints enforce active-workspace ownership for the dataset and audits.

## Governance
Version records are immutable audit snapshots. Cross-workspace dataset or audit IDs return not found and cannot be compared.

## Future foundations
The version model provides the baseline for schema drift monitoring, scheduled audits, alerting, and trend reporting.

## Feature 18.2 corrections

- Compare Versions now provides visible loading, success, validation, and API error states.
- Comparison rendering safely handles empty issue collections.
- Version History uses neutral snapshot styling with no green row background.
- Page and card headers use one compact, consistent size and weight.
