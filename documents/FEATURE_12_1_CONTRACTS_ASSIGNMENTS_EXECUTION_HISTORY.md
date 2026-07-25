# Feature 12.1 — Contracts, Assignments and Execution History Completion

## Overview

Feature 12.1 completes the remaining operational areas of the Rules & Contracts Workspace. It expands Data Contracts, Dataset Assignments, and Execution History from supporting views into functional governance workspaces backed by persistent APIs and database records.

The feature allows teams to define dataset expectations, maintain contract versions, validate contracts against current audits, manage rule coverage individually or in bulk, and investigate historical rule performance using filters, exports, audit drill-down, and interactive Chart.js visualizations.

## Data Contract Management

Data contracts are now stored as persistent, workspace-scoped governance records rather than being available only as temporary audit-generated documents.

Each contract includes:

- Contract name and description
- Registered dataset
- Draft, published, or archived status
- Version number
- Required columns
- Expected data types
- Allowed values
- Numeric and date ranges
- Unique columns
- Sensitive-column declarations
- Source audit
- Validation status and results

Contracts can be created manually or generated from the latest completed dataset audit.

## Contract Versioning

Editing a contract creates a new version while preserving earlier definitions.

The version history records:

- Version number
- Status
- Contract definition
- Creation time
- Source audit
- Description

This provides traceability when reliability expectations or dataset schemas change.

## Contract Validation

A contract can be validated against the latest completed audit for its dataset.

Current validation checks include:

- Required-column presence
- Expected data-type compatibility
- Missing schema requirements
- Type mismatches
- Total violation count

The result is stored as passed or failed and remains visible in the contract registry and detail panel.

## Contract Workspace Experience

The Data Contracts tab now provides:

- Contract summary metrics
- Searchable contract registry
- Selected contract detail panel
- Requirement summary
- Contract-definition preview
- Generate-from-audit action
- Contract editor
- Validation action
- Version-history view
- Draft, published, and archived states

## Dataset Assignment Management

The Assignments tab provides a complete view of rule coverage across registered datasets.

Users can:

- Review rules grouped by dataset
- Assign an individual rule to a dataset
- Remove an existing assignment
- Select multiple rules and datasets
- Apply assignments in bulk
- Remove assignments in bulk
- Search datasets and assigned rules
- Review assignment totals and coverage rate

Assignments remain workspace-scoped and only active assignments are evaluated during audits.

## Assignment Coverage Metrics

The workspace displays:

- Total active assignments
- Number of datasets covered
- Number of rules assigned
- Dataset coverage percentage

These metrics help identify datasets that are not yet protected by quality rules.

## Execution History

The Execution History tab provides searchable evidence of rule evaluations across audit runs.

Each execution record includes:

- Rule name
- Dataset name
- Pass or fail outcome
- Affected-row count
- Affected-row percentage
- Execution message
- Execution timestamp
- Related audit

Users can open the related audit directly from an execution record.

## Execution Filters and Pagination

Execution history can be filtered by:

- Rule name search
- Outcome
- Rule
- Dataset

The result table includes client-side pagination and a clear-filter action for returning to the complete history.

## Execution Export

Execution evidence can be exported as a CSV file for external analysis, governance reviews, or stakeholder reporting.

The export includes:

- Rule
- Dataset
- Outcome
- Affected rows
- Affected rate
- Execution time
- Audit identifier

## Chart.js Visualizations

The Execution History tab uses Chart.js for interactive visual analysis.

Current charts include:

- Pass-versus-fail outcome distribution
- Failure trend across execution dates

The charts update from live rule-execution records and support responsive resizing and hover tooltips.

## API and Backend Support

Feature 12.1 introduces persistent contract, bulk-assignment, execution-query, and export operations.

Key endpoints include:

```text
GET    /quality-rules/contracts
POST   /quality-rules/contracts
POST   /quality-rules/contracts/generate/{dataset_id}
GET    /quality-rules/contracts/{contract_id}
PATCH  /quality-rules/contracts/{contract_id}
GET    /quality-rules/contracts/{contract_id}/versions
POST   /quality-rules/contracts/{contract_id}/validate

POST   /quality-rules/assignments/bulk

GET    /quality-rules/executions
GET    /quality-rules/executions/export.csv
```

## Database Support

Feature 12.1 adds the `data_contracts` table.

The table stores:

- Workspace and dataset ownership
- Contract identity
- Version history
- Contract JSON definition
- Status
- Source audit
- Validation result
- Publication and validation timestamps
- Creation and update metadata

## Security and Governance

The completed workspace includes:

- Authenticated access
- Workspace isolation
- Role-protected contract and assignment changes
- Persistent contract versions
- Validation evidence
- Rule-to-dataset traceability
- Audit-linked execution evidence
- Exportable governance history

## Foundation for Future Features

Feature 12.1 provides the foundation for:

- Reliability Scoring Improvements
- Contract-driven audit enforcement
- Contract approval workflows
- Schema-drift monitoring
- Rule effectiveness analysis
- Governance dashboards
- Scheduled contract validation
- Issue Lifecycle Management

## Contract Lifecycle Validation Update

The contract registry now displays only the latest contract version for each dataset while preserving every earlier version in Version History. Generating or manually creating another contract for a governed dataset extends the same contract lineage instead of creating a separate independent record.

Contract generation now uses an in-application dataset selector showing the latest audit and existing contract state. Selected contracts also support publish, archive, and return-to-draft lifecycle actions, with each transition recorded as a new immutable contract version.
