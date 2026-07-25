# Feature 21 — Alerts & Notifications

## Overview
Feature 21 adds a workspace-scoped alert center for reliability risks and operational monitoring events.

## Alert sources
- Reliability score threshold breaches
- Critical and high-severity audit issues
- Quality rule failures
- Data contract validation failures
- Scheduled audit failures

## Alert lifecycle
Alerts support unread/read, acknowledged, resolved, dismissed, and reopened states. Each transition is persisted and scoped to the active workspace.

## Workspace experience
The Alerts & Notifications page provides summary metrics, search, severity/status/type/dataset filters, tabs, pagination, alert details, direct audit navigation, and CSV export.

## Preferences
Each user can configure score thresholds, in-app notifications, email readiness, and severity preferences. Email delivery is intentionally provider-ready rather than externally delivered in the local baseline.

## Security and governance
Alert reads and writes verify the active workspace. Cross-workspace alert identifiers are not accessible.

## Feature 21.1 UI refinement

- Replaced filled lifecycle-tab buttons with the approved underline navigation treatment.
- Standardized the alert search field with the other filter controls.
- Removed filled green backgrounds from alert row and lifecycle action controls.
- Retained accessible active, hover, focus, severity, and status states.
