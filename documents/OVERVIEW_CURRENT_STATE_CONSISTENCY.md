# Overview Current-State Consistency

## Purpose

This update separates current operational posture from historical execution totals in the Overview command centre.

## Corrected metrics

- Active issues use only the latest audit for each dataset.
- Issue lifecycle totals use the same current issue set as the active-issue card.
- Open issues map to the New lifecycle state; resolved, fixed, accepted, dismissed, and closed items map to Resolved.
- Failed rules and failure rate use only rule executions from each dataset's latest audit.
- Contract Violations reports the current validation finding count; Contracts Impacted reports affected contract lineages.
- Schema drift is deduplicated by currently affected dataset.
- Dataset Versions counts immutable imported source revisions, not audit reruns.
- Audits This Week counts completed audit records.
- Audit Success Rate treats a stored AuditRecord as a successful execution and includes failed scheduled attempts in the denominator.
- Contract totals count only the latest version of each contract lineage.

## UI corrections

- Platform Summary values share consistent icon, label, and value rows.
- Summary cells support narrow widths without overflowing.
- Action Points wraps safely inside its summary cell.
- Contract findings retain dataset-version context after validation.
- Expected and observed contract finding values are more descriptive.

## Data preservation

No migration is required. The update does not include or replace `data`, `runtime`, or `.venv`.
