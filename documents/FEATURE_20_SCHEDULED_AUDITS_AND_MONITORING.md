# Feature 20 — Scheduled Audits and Monitoring

## Overview

Feature 20 adds workspace-scoped recurring audit automation and a monitoring workspace modeled on the approved Scheduled Audits dashboard.

## Core capabilities

- Daily, weekly, and monthly schedules
- Dataset-specific run time configuration
- Pause, resume, delete, and run-now controls
- Automatic execution of due schedules when monitoring refreshes
- Persisted execution history and failure evidence
- Latest score, issue count, run duration, and audit link
- Upcoming-run queue
- Seven-day completed and failed metrics
- Chart.js score, execution, and issue trends

## Navigation and workspace UX

The application shell now groups navigation into Overview, Data Management, Automation, Governance, and Administration. The active workspace selector is placed at the bottom of the sidebar, matching the approved mockup.

## APIs

- `GET /schedules`
- `POST /schedules`
- `POST /schedules/{schedule_id}/run`
- `PATCH /schedules/{schedule_id}/status`
- `DELETE /schedules/{schedule_id}`

## Persistence and governance

Schedules and execution runs are stored in dedicated database tables. Every read and write is restricted to the active workspace. Schedule management requires Owner or Admin permissions.

## Execution model

A schedule reruns the latest persisted source file for its dataset, executes assigned rules, persists the resulting audit, updates the dataset registry, and records execution status. Due schedules are processed during monitoring refreshes; a production deployment can later move the same execution service into a dedicated worker.


## Feature 20.2 corrections

- Scheduled run scores are persisted as numeric overall scores rather than schema objects.
- Run-now completion reliably updates execution history, metrics, and linked audit navigation.
- The schedule form error banner is hidden until a real validation or backend error occurs.

## Feature 20.3 UX corrections
- Schedule actions use neutral accessible controls.
- Upcoming runs include a working calendar dialog.
- Schedule deletion uses an in-app confirmation dialog and preserves existing audit history.

## Feature 20.4 refinements

- Added an application background scheduler that polls for due active schedules every 10 seconds and executes them without requiring the Scheduled Audits page to be open.
- Added duplicate-run protection for schedules already being processed in the current application process.
- Replaced the upcoming-run list dialog with a navigable full-month calendar. Scheduled dates are highlighted and expose run details on hover or keyboard focus.
- Replaced text glyph actions with consistent inline SVG run, pause/resume, dataset, and overflow icons.
- Refined the Audit Schedules table with aligned headers, compact two-line frequency/date cells, clearer result presentation, and neutral action controls.


## Feature 20.5 UI refinements

- Added a visible trash action for every schedule row.
- Refined the monthly calendar container with consistently rounded corners and internal scrolling.
- Replaced colored month navigation controls with neutral inline arrows aligned to the month label.

## Feature 20.6 reliability corrections

- Audit times are stored as UTC but created from the user's browser-local wall clock and timezone offset.
- Existing schedules without timezone metadata are repaired when the Scheduled Audits workspace first loads.
- The background worker checks due active schedules every 10 seconds and runs them without requiring the page to remain open.
- Scheduled table times use a consistent 24-hour display so the selected time and next-run time match visibly.
- The schedule action area always exposes Run, Pause/Resume, and Delete without clipped controls.
- The monthly calendar uses a compact rounded dialog with top-right close control and hover/focus run details.
