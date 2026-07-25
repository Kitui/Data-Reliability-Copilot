# Feature 17.4 — Remediation Score Risk Handling

## Overview

Corrects projected-score communication and adds a guarded apply flow when selected remediation actions are expected to reduce reliability.

## Score presentation

- Score change is calculated as projected score minus current score.
- Positive, neutral, and negative changes use the correct sign.
- Negative projections show `Risk review required` instead of `Preview ready`.
- A warning explains the projected decrease and affected scores.

## Apply protection

Before applying changes, the platform recalculates the preview using the current selection. When the projected score is lower, the user must explicitly confirm creation of the governed dataset copy.

## UX behavior

- Negative score changes use warning styling.
- The apply action changes to a warning state.
- Cancelling confirmation leaves the original dataset unchanged.
- Safe or improving projections continue without additional confirmation.
