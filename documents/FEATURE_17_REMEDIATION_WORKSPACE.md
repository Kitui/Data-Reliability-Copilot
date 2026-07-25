# Feature 17 — Remediation Workspace

## Overview
Feature 17 turns remediation recommendations into a controlled correction workflow. Users can select audit issues, preview deterministic transformations, estimate reliability impact, apply approved corrections to a separate dataset copy, re-audit the result, and export the cleaned CSV.

## Core Capability
- Builds remediation actions from the active audit.
- Supports deduplication, missing-value handling, value standardization, and sensitive-data masking.
- Keeps validity, integrity, schema, and other high-risk fixes as review-only actions.
- Never overwrites the original uploaded dataset.

## Functional Areas
### Action Selection
Users select only the issue-level actions they intend to test or apply. Risk and generated Pandas guidance remain visible for every action.

### Impact Preview
The backend applies selected actions to an isolated dataframe copy and runs a projected audit. The preview reports:
- Projected reliability score and score delta
- Projected open issues
- Rows retained or removed
- Changed cells and columns
- Before-and-after sample values
- Review-only warnings

### Apply to Dataset Copy
Approved actions create a new cleaned CSV, a new governed audit, and a new dataset registry entry. The original audit and source file remain unchanged.

### Export and Revalidation
The cleaned CSV can be exported directly. The newly created audit can be opened immediately for validation, comparison, issue review, and evidence capture.

## UX
The full-page Remediation Workspace contains:
- Action and strategy controls
- Impact metrics
- Before-and-after samples
- Warning and success states
- Generated cleaning script
- Export and corrected-audit actions

## API and Backend
- `GET /audits/{audit_id}/remediation`
- `POST /audits/{audit_id}/remediation/preview`
- `POST /audits/{audit_id}/remediation/apply`
- `GET /audits/{audit_id}/source.csv`

Every endpoint enforces active-workspace isolation.

## Governance and Safety
- Corrections are applied only to copies.
- Destructive or ambiguous actions remain review-only.
- Sensitive-field masking must be explicitly selected.
- Corrected outputs retain an audit trail through a new audit ID and source-audit reference in the apply response.

## Future Foundations
This feature prepares the platform for reusable remediation recipes, approval workflows, automated revalidation policies, dataset lineage, and scheduled remediation runs.
