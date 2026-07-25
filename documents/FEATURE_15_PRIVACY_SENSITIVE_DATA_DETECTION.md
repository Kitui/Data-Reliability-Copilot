# Feature 15 — Privacy and Sensitive-Data Detection

## Overview

Feature 15 adds automated privacy intelligence to Data Reliability Copilot. It identifies columns that are likely to contain personal, financial, government-issued, contact, or network-identifying data and records the result as part of the dataset profile and audit.

## Detection Engine

The detector combines column-name signals with sampled value-pattern analysis. It supports common sensitive-data classes including email addresses, phone numbers, personal names, postal addresses, dates of birth, government identifiers, payment cards, financial accounts, IP addresses, and identifier-like fields.

## Classification and Confidence

Each detected column receives:

- A privacy classification
- A low, medium, high, or critical sensitivity level
- A confidence score
- Explainable detection reasons
- A recommended masking or tokenisation action

## Audit Integration

Sensitive columns generate column-specific privacy findings during an audit. These findings appear with other quality issues, contribute to reliability scoring, and remain available for investigation, lifecycle management, reporting, and remediation.

## Dataset Intelligence

Dataset profiles now include the number of sensitive columns and the highest sensitivity level found. Column profiles retain their privacy classification, confidence, reasoning, and masking recommendation.

## API Support

Privacy intelligence is available through:

```text
GET /datasets/{dataset_id}/privacy
```

The endpoint returns the latest sensitive-column classifications for the selected workspace dataset.

## Security and Data Handling

Detection is performed locally against dataset values. Privacy findings contain classifications and recommendations rather than exposing raw sampled values through the privacy endpoint.

## Foundation for Future Features

This feature supports privacy-focused rules, masking workflows, remediation recipes, access-control recommendations, governance reporting, and sensitive-data monitoring.

## Privacy Issue Investigation

Privacy findings now expose column-level intelligence directly in the Audit Workspace. Each detected sensitive column shows its classification, sensitivity, confidence, detection reasons, and recommended protection control.

Privacy findings cannot be resolved through a generic automatic recommendation. Users must first record the implemented control—such as masking, tokenization, encryption, or restricted access—and provide validation evidence. The control can then be applied and preserved in the issue lifecycle history.
