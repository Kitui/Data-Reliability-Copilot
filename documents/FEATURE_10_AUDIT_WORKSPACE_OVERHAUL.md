# Feature 10 — Audit Workspace Overhaul

## Overview

Feature 10 transforms the Audit Workspace into the central operational area for running audits, reviewing reliability results, investigating dataset issues, and taking follow-up action. It replaces the earlier workbench-first experience with a focused dashboard based on saved datasets and audit runs.

## Audit Execution and Run Selection

Users can upload a CSV or run the sample audit directly from the workspace. Saved audit runs are grouped by dataset, allowing users to switch between datasets and historical runs without leaving the page.

Each selected run displays its creation time, reliability score, scanned rows and columns, duplicate-row count, and completion status.

## Reliability and Issue Summary

The workspace provides immediate visibility into:

- Overall reliability score and risk level
- Total detected issues
- Critical and high-priority issues
- Medium-severity issues
- Low-severity findings
- Number of quality checks evaluated

Issue distributions are calculated from the selected audit rather than using placeholder dashboard values.

## Issue Intelligence

Audit findings are summarized through:

- Severity distribution
- Category distribution
- Most impacted columns
- A searchable and filterable issue explorer

The issue explorer shows severity, category, triggered check, affected columns, description, affected rows, affected percentage, and current workflow status.

## Issue Investigation and Status Management

Selecting an issue displays its detailed finding and recommended action. Users can update an issue status directly from the table, and the change is persisted through the existing audit issue API.

The workspace supports filtering by severity and category, free-text search, and quick filter clearing.

## Reports, Comparison, and Remediation

Users can open the full audit report, compare the selected audit with the previous run for the same dataset, and retrieve the generated remediation plan.

Comparison summaries highlight score changes, issue-count changes, new issues, and resolved issues. Remediation summaries surface the number and type of recommended corrective actions.

## API and Backend Support

The workspace uses the existing governed audit APIs for:

- Listing saved audits
- Loading a complete audit result
- Running CSV and sample audits
- Updating issue workflow status
- Generating HTML reports
- Comparing audit runs
- Retrieving remediation plans

All audit access remains scoped to the active workspace.

## User Experience

The redesigned workspace uses the established Data Reliability Copilot design system with compact metric cards, full-page navigation, responsive filtering, internally scrollable analysis panels, and clear visual severity indicators.

The interface is populated entirely from live audit results and preserves browser routing through the existing application shell.

## Foundation for Future Features

Feature 10 provides the operational foundation for:

- Quality Rule Engine
- Rules and Contracts Workspace
- Reliability Scoring Improvements
- Issue Lifecycle Management
- Privacy and Sensitive-Data Detection
- Remediation Workspace
- Audit reporting and monitoring

## Interactive Visual Analysis

The severity and category summaries use Chart.js to provide responsive, interactive visualizations. Tooltips show exact issue counts and proportions, while selecting chart segments or bars filters the issue explorer to the chosen severity or category.

## Recommendation Application

A selected issue includes an **Apply Recommendation** action. Applying it records the recommendation as completed, marks the issue as fixed, removes its active impact, recalculates the reliability score and summary, and immediately refreshes the dashboard metrics, charts, and issue explorer.

## Issue Readability

Issue titles, affected-column names, and descriptions support text wrapping so long values remain readable without breaking the table layout.
