# Feature 19.1 — True Dataset Version Ingestion

## Overview
Feature 19.1 introduces immutable CSV revisions inside an existing dataset lineage. A user selects a registered dataset and imports a changed CSV as its next version rather than creating an unrelated registry entry.

## Core workflow
- Select a dataset in the Dataset Registry.
- Choose **Import new version**.
- Upload a CSV revision.
- Preserve the existing dataset identity and ordered audit lineage.
- Run a complete audit automatically.
- Execute active assigned quality rules.
- Update the dataset's latest score, schema, row count, and issue count.
- Compare the new audit-backed version with the preceding version in Dataset Versions and Schema Drift Monitoring.

## Governance and isolation
Version imports are restricted to the active workspace. The source file is stored as an immutable upload, and each revision receives its own audit identifier and timestamp. Existing versions and source datasets are not overwritten.

## Schema drift foundation
Schema Drift Monitoring now receives meaningful events when imported revisions add or remove columns, change inferred types, alter missing-value rates, or materially shift cardinality.
