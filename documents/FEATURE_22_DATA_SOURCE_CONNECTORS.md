# Feature 22 — Data Source Connectors

## Overview
Adds a workspace-scoped connector registry for governed external data-source connections.

## Supported connector profiles
BigQuery, PostgreSQL, MySQL, Google Sheets, Google Cloud Storage, and REST API.

## Capabilities
- Create and configure connector records
- Test connectivity and retain health evidence
- Trigger synchronization and record activity
- Filter, inspect, export, and delete connectors
- Workspace isolation and Owner/Admin write permissions
- Credential references are stored as hints only; secrets belong in a production secret manager

## Future foundations
Provider-specific clients, encrypted credentials, background synchronization, dataset discovery/import, and cloud secret-manager integration.
