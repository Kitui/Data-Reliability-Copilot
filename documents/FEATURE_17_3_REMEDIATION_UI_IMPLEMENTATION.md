# Feature 17.3 — Remediation Workspace UI Implementation

## Overview

Implements the approved Remediation Workspace mockup as a dedicated full-page workflow while preserving the existing remediation backend and audit integration.

## Workspace structure

- Four-step remediation progress indicator
- Dataset and audit summary strip
- Grouped recommended fixes with risk and review indicators
- Missing-value and sensitive-data controls
- Before-and-after impact comparison
- Estimated issue-reduction visualization
- Transformation sample table
- Generated Pandas cleaning script
- Output, validation, export, and corrected-audit controls

## Functional behavior

- Existing audit remediation actions load automatically.
- Actions can be selected individually or cleared together.
- Preview recalculates projected score, issue count, changed cells, and removed rows.
- Applying remediation creates a governed dataset copy and reruns validation.
- The original dataset remains unchanged.
- Export and corrected-audit navigation remain available after application.

## UX approach

Typography is deliberately restrained: compact headings, regular body weights, limited emphasis, and no oversized metric text. The layout adapts from three columns on large screens to one column on smaller screens.
