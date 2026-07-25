# Feature 11 — Quality Rule Engine

## Overview

Feature 11 introduces a reusable Quality Rule Engine for defining, assigning, executing, and monitoring data-quality rules. It replaces one-off audit configuration with persisted rules that can be consistently applied to selected datasets across repeated audit runs.

## Rule Definition

Quality rules store the rule name, description, type, scope, affected column, category, severity, parameters, recommendation, and active status. Rules are isolated by workspace and can be maintained independently from audit runs.

## Supported Rule Types

The engine currently supports required values, uniqueness, email validation, approved values, regular-expression patterns, numeric ranges, text-length ranges, missing-value thresholds, expected data types, freshness windows, and duplicate-row detection.

## Dataset Assignment

Rules can be assigned to individual registered datasets. Only active rules and active assignments are executed, allowing teams to control which checks apply to each dataset without changing application code.

## Rule Execution

Assigned rules run automatically during new audits. Every execution records a pass or fail outcome, affected-row count, affected percentage, execution message, and timestamp. Failed rules generate traceable audit issues linked back to the originating rule.

## Audit Integration

Rule-generated issues participate in reliability scoring, summaries, reports, visualizations, remediation planning, and issue investigation alongside the platform’s built-in deterministic findings.

## API and Backend Support

The feature adds APIs for rule creation, listing, retrieval, updating, deletion, dataset assignment, unassignment, and execution history. Database tables persist rule definitions, dataset assignments, and audit-level execution outcomes.

## Governance and Access Control

Rules are workspace-scoped. Owners, administrators, and analysts can create and assign rules, while deletion is restricted to owners and administrators. Viewers retain read-only access to the rule library and execution results.

## Foundation for Future Features

Feature 11 provides the backend foundation for the Rules & Contracts Workspace, custom visual rule builder, rule effectiveness monitoring, contract validation, improved reliability scoring, and automated rule recommendations.
