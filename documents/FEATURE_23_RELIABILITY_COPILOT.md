# Feature 23 — Reliability Copilot

## Overview
Reliability Copilot is a workspace-scoped, evidence-grounded assistant for explaining audit results, reliability scores, issue patterns, quality-rule failures, contract violations, schema drift, and remediation priorities.

## Core capability
- Three-panel context, conversation, and evidence workspace
- Saved Copilot sessions and messages
- Dataset, audit, comparison, and analysis-mode context
- Deterministic platform-grounded analysis using persisted DRC evidence
- Score, issue, rule, contract, and drift summaries
- Recommended human-reviewed actions
- Direct links to audits, datasets, comparisons, rules, and remediation
- Governed Action Point creation

## Governance and security
Copilot is read-only by default, workspace isolated, and does not publish rules or alter datasets. Rule drafts and remediation remain subject to existing human review and approval workflows.

## Future foundation
The response engine is provider-agnostic and can later route masked evidence to an approved LLM provider while retaining the same evidence model, guardrails, and persistence layer.

## Feature 23.1 corrections

- Copilot context selectors now default to the active dataset and latest completed audit when workspace evidence exists.
- Empty workspaces show explicit disabled selector states instead of blank controls.
- Greetings and conversational prompts receive a conversational response without fabricated audit analysis.
- Evidence analysis is generated only when a completed audit is available.
- Status messages safely normalize structured API errors instead of rendering `[object Object]`.
