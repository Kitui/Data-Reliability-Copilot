# Dataset Version and Audit Separation

## Correct behavior

- Import CSV creates dataset version 1.
- Import new version creates the next immutable dataset version.
- Manual reruns, scheduled audits, rule re-evaluations, and remediation checks create audit executions only.
- Audit executions do not increase the dataset version number or create schema-drift comparisons.

## Existing database compatibility

No migration is required. Older audit history is reconstructed using source-file lineage so repeated audits of the same source do not inflate the version count. Existing accounts, datasets, rules, contracts, audits, and uploads remain intact when the update is overlaid without replacing `data/`.
