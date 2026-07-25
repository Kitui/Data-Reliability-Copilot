# Rule-Aware Contract Generation

Contract generation now combines the latest audited dataset schema with the dataset's active assigned quality rules.

## Enforcement sources

- Dataset audit: column names, inferred types, PII classifications.
- Active assigned rules: required fields, uniqueness, allowed values, numeric ranges, formats, length limits, missing thresholds, expected types, and freshness windows.
- Observed profiling values: retained only under `profile_summary`; they are not enforced as approved limits.

This prevents anomalous values such as negative ages, future dates, invalid country codes, or excessive scores from becoming valid contract thresholds merely because they were present in the source data.

No migration is required. Existing databases and uploaded datasets remain compatible.
