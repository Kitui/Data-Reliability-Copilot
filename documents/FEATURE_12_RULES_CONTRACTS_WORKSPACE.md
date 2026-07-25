# Feature 12 — Rules & Contracts Workspace

## Overview

Feature 12 provides a full operational workspace for managing data-quality rules, dataset assignments, execution evidence, and generated data contracts. It turns the Quality Rule Engine introduced in Feature 11 into a practical user-facing governance experience.

## Rule Library

The Rule Library lists all workspace-scoped quality rules with their scope, target column, category, severity, activation state, assignment coverage, and latest execution time. Users can search and filter the library by scope, category, severity, and status.

## Rule Creation and Editing

Authorized users can create, update, activate, deactivate, and delete rules through a structured editor. The editor supports rule type, scope, target column, severity, category, JSON parameters, recommendations, and lifecycle status.

## Dataset Assignments

Rules can be assigned to one or more registered datasets. The Assignments view shows current coverage and allows users to add or remove dataset assignments without leaving the workspace.

## Data Contracts

The Data Contracts view exposes contract availability for registered datasets. Contracts are generated from the latest audit evidence and contain structural expectations such as required columns, unique keys, expected types, allowed values, ranges, freshness rules, and identified sensitive fields.

## Execution History

The Execution History view records rule outcomes across audit runs, including pass or fail status, affected rows, affected rate, execution time, and audit reference. This provides traceability and evidence for governance and rule-effectiveness analysis.

## Interactive Analytics

The workspace uses Chart.js for all visual analytics. It includes an interactive category-distribution doughnut chart and a horizontal bar chart showing the most frequently failing rules. Charts update from live rule and execution data.

## API and Backend Support

The feature uses the existing quality-rule management and assignment APIs and adds a dashboard endpoint that aggregates rules, assignments, metrics, and execution activity for the active workspace.

```text
GET /quality-rules/dashboard
```

## Security and Governance

All rules, assignments, contracts, and execution evidence remain authenticated and workspace-scoped. Rule creation and assignment actions respect existing role-based permissions.

## Foundation for Future Features

Feature 12 provides the user-facing foundation for custom rule building, contract validation, reliability scoring improvements, rule effectiveness tracking, scheduled audits, and governance reporting.
