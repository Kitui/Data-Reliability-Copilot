# Feature 22 — Connectors

## Overview

Connectors provides a workspace-scoped registry for external data-source configurations used by datasets, audits, and monitoring.

## Supported source types

- PostgreSQL
- MySQL
- BigQuery
- Google Sheets
- Google Cloud Storage
- REST API

## Core capability

- Create, edit, activate, deactivate, test, sync, and delete connectors
- Search, filter, paginate, and export the connector registry
- Track health, test evidence, sync status, and sync history
- Register connected datasets without duplicating existing workspace datasets
- Restrict configuration changes to Owners and Admins
- Isolate connector configurations and activity by workspace

## UX

The workspace follows the approved two-panel design with summary metrics, a compact connector table, SVG source and action icons, and a detailed connector evidence panel.

## Security and governance

Connector configuration and credential payloads are persisted separately. Credential values are never returned by connector read APIs. Production deployments should replace local credential persistence with a managed secret provider.

## Future foundations

- Connector-specific schema discovery
- Incremental synchronization and checkpoints
- Background sync scheduling
- OAuth and cloud service-account workflows
- Full ingestion and automatic audit execution after sync
