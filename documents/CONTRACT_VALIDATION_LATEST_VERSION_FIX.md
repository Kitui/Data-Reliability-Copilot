# Contract Validation Latest-Version Fix

Contract validation now resolves the latest completed audit for the latest imported dataset version instead of reusing the audit that originally generated the contract.

## Validation behavior

- Uses the latest dataset version and its newest completed audit.
- Evaluates required columns and expected types.
- Evaluates every active assigned rule captured in the contract.
- Records detailed findings with rule, column, affected rows, rate, and message.
- Updates the contract source audit to the audit actually validated.
- Does not create a dataset or contract version.
- Displays validation findings in the contract detail panel.

The update does not require a database migration and is packaged without runtime data so an existing `data/drc.db` can be retained.
