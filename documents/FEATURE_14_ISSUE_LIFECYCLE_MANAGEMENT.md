# Feature 14 — Issue Lifecycle Management

## Overview

Feature 14 turns audit findings into managed operational work. Issues can now move through a controlled lifecycle with ownership, severity, due dates, investigation notes, resolution evidence, and a permanent activity history.

## Lifecycle States

Issues support open, triaged, in-progress, blocked, resolved, accepted-risk, and ignored states. Resolved and ignored findings remain available for historical evidence but no longer reduce the active reliability score.

## Ownership and Prioritization

Each issue can be assigned to an owner, given a due date, and have its severity changed as investigation reveals more context. These changes are persisted with the audit and immediately update reliability scoring and dataset health.

## Investigation and Resolution

Users can record investigation notes, resolution details, and supporting evidence. Resolving an issue requires a resolution note, helping ensure that quality improvements remain explainable and reviewable.

## Activity History

Every field update, comment, reopen action, and applied recommendation creates an immutable activity entry containing the actor, time, changed field, previous value, new value, and supporting note.

## Audit Workspace Integration

The Selected Issue card now provides the core lifecycle controls directly inside the Audit Workspace. Users can update status, severity, ownership, due date, notes, evidence, and comments without leaving the audit context.

## API and Backend Support

```text
PATCH /audits/{audit_id}/issues/{issue_id}
GET   /audits/{audit_id}/issues/{issue_id}/lifecycle
POST  /audits/{audit_id}/issues/{issue_id}/comments
POST  /audits/{audit_id}/issues/{issue_id}/apply-recommendation
```

## Security and Governance

Lifecycle records are authenticated and workspace-scoped. Historical audit issues are retained, while activity records provide traceability for operational and governance reviews.

## Foundation for Future Features

This feature provides the workflow foundation for remediation tasks, accepted-risk approvals, notifications, service-level tracking, team collaboration, and executive reliability reporting.
