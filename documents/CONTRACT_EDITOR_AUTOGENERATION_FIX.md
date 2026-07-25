# Contract Editor Auto-generation Fix

## Purpose

The Create Contract dialog now builds its JSON definition automatically from the selected dataset's latest completed audit.

## Behaviour

- Opening **Create Contract** loads the selected dataset's generated contract definition.
- Changing the dataset regenerates the definition from that dataset's latest audit.
- Existing contracts continue to load their stored definition when creating a new version.
- Datasets without a completed audit show a clear instruction instead of silently leaving `{}`.
- The definition remains editable before the contract version is saved.
- The contract dialog now clips its content inside consistently rounded edges and scrolls internally.

## Existing data

No database migration is required. Keep the existing `data/drc.db` and `data/uploads` directory to preserve users, datasets, rules, audits, and test progress.
