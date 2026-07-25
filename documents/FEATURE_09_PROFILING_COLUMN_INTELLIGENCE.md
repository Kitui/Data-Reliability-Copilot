# Feature 09 — Profiling Engine and Column Intelligence

This feature restructures dataset profiling into focused modules for type inference, statistics, risk signals, and profile orchestration. Each audited column now includes cardinality, missing-value risk, numeric outliers, identifier likelihood, constant-value detection, descriptive statistics, and an explainable low, medium, or high risk classification.

The Dataset Schema card displays the richer intelligence while preserving the existing compact, scrollable layout. A dedicated dataset-intelligence API also makes the latest profile available to future Audit, Rules, Privacy, and Remediation features.
