# Feature 16 — Custom Rule Builder

## Overview

Feature 16 introduces a guided, no-code workflow for creating reusable data-quality rules. Users can select a dataset, choose a target column, configure validation conditions, test the rule against real data, review its estimated impact, and save it directly to the Rule Library.

## Guided Rule Configuration

The builder supports dataset and column selection, rule type, category, severity, scope, recommendation, and activation status. Parameter fields change automatically for the selected rule type, reducing the need to edit JSON manually.

Supported guided configurations include allowed values, regular expressions, numeric ranges, text-length limits, missing-value thresholds, expected types, and freshness windows.

## Dataset and Column Context

The builder loads columns from the selected dataset’s latest audit profile. Each available column includes its inferred type, allowing rules to be targeted using current dataset intelligence rather than manually entered field names.

## Rule Testing and Impact Preview

Unsaved rules can be executed against the selected dataset before they are committed. The preview reports:

- Pass or fail outcome
- Affected row count
- Affected percentage
- Total tested rows
- Safe failing examples
- Estimated reliability-score impact

Testing does not modify the dataset, audit history, or Rule Library.

## Rule Saving and Assignment

A successfully configured rule can be saved to the existing Quality Rule Engine. Users may also assign the new rule to the selected dataset immediately, allowing it to execute automatically during future audits.

Saved rules remain available for editing, activation, deactivation, assignment, execution tracking, and governance through the Rules & Contracts Workspace.

## API Support

Feature 16 adds:

```text
GET  /quality-rules/builder/context/{dataset_id}
POST /quality-rules/builder/test
```

The context endpoint returns safe dataset and column metadata. The test endpoint evaluates an unsaved rule against the latest available source data and returns an impact preview without persisting an execution.

## Security and Validation

Builder operations require authenticated workspace access. Rule testing validates dataset ownership, rule structure, required parameters, target-column availability, and source-file availability.

Raw dataset values are not exposed beyond limited safe failing examples returned to the authenticated user.

## Integration with Existing Features

The Custom Rule Builder integrates with:

- Dataset Registry
- Profiling and Column Intelligence
- Quality Rule Engine
- Rules & Contracts Workspace
- Audit Workspace
- Reliability Scoring
- Rule Execution History

## Foundation for Future Features

Feature 16 provides the foundation for rule templates, AI-assisted rule suggestions, rule creation from audit issues, reusable business-rule packs, and contract-to-rule generation.
