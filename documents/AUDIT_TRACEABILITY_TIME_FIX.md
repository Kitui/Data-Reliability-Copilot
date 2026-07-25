# Audit Traceability and Time Fix

The Audit Workspace now identifies the immutable dataset revision used by each run.

## Changes

- Shows dataset version and source file in Audit Run Details.
- Treats timezone-naive server timestamps as UTC and displays them in `Africa/Nairobi`.
- Uses the same time formatter in the audit-run selector and issue activity history.
- Prevents boolean/status metadata fields such as `email_verified` from being audited as email addresses or classified as email PII.

No database migration is required. Existing audit history remains valid; rerunning the latest audit removes the previous `email_verified` false positive from the new run.
