# Data Reliability Copilot

**Data Reliability Copilot (DRC)** is a production-oriented data reliability, quality, governance, remediation, and operational intelligence platform.

It helps teams register datasets, profile data, enforce reusable quality rules and contracts, detect schema drift, manage issues, coordinate remediation, automate audits, generate alerts and reports, and use a context-aware Reliability Copilot to support human-led decisions.

## Platform Overview

DRC provides one governed workflow for the complete data reliability lifecycle:

```text
Dataset registration
        ↓
Profiling and privacy detection
        ↓
Quality rules and data contracts
        ↓
Audit execution and reliability scoring
        ↓
Issue, alert, and schema-drift management
        ↓
Remediation and controlled revalidation
        ↓
Reports, operational summaries, and Copilot guidance
```

The platform is workspace-scoped, database-backed, deterministic-first, and designed to preserve traceability across datasets, imported versions, audits, rules, contracts, findings, and remediation activity.

## Core Capabilities

### Data management

- CSV dataset registration and import validation
- Dataset preview, schema inspection, and column intelligence
- Dataset ownership, domain, environment, and source metadata
- Immutable source-version lineage
- Import-new-version workflow
- Audit-to-audit and version-to-version comparison
- Schema drift detection

### Profiling and privacy

- Data-type inference
- Missingness and uniqueness analysis
- Numeric, categorical, date, and text statistics
- Outlier and anomaly detection
- Sensitive-data and PII classification
- Column-level privacy recommendations and evidence tracking

### Quality rules and contracts

- Reusable workspace quality rules
- Dataset-rule assignments
- Rule categories including completeness, validity, uniqueness, consistency, timeliness, integrity, and privacy
- Required-value, unique-value, email-format, allowed-value, regex, numeric-range, text-length, expected-type, freshness, duplicate-row, and missing-threshold checks
- Rule execution history
- Rule-aware data-contract generation
- Contract publication, versioning, validation, and archival
- Paginated contract validation findings

### Audits and scoring

- Manual and scheduled audits
- Transparent reliability scoring
- Severity-aware and breadth-aware issue scoring
- Current and historical audit comparison
- Issue filtering by severity, category, dataset, and audit run
- Exact audit traceability to dataset version and source file
- Audit status and execution history

### Issue lifecycle and remediation

- New, in-progress, resolved, reopened, accepted-risk, and dismissed states
- Owner, severity, due date, notes, evidence, and activity history
- Human-reviewed issue intelligence
- Recommended remediation actions
- Controlled impact preview
- Generated Pandas cleaning scripts
- Governed cleaned-dataset copies
- Follow-up audit and revalidation workflows

### Automation and monitoring

- Scheduled audits with timezone support
- Alerts for rule failures, high-severity issues, contract failures, score degradation, and schema drift
- Alert lifecycle: new, read, acknowledged, resolved, and dismissed
- Data-source connector registry and test/synchronisation flows
- Upcoming-run visibility from the Overview command centre

### Reliability Copilot

- Workspace, dataset, audit, issue, and contract context
- Conversational audit and reliability guidance
- Session history and deletion
- Structured Action Points
- Human approval and guardrail-oriented workflow
- Deterministic fallback when an external model is unavailable

### Reporting and executive visibility

- Platform-wide Overview command centre
- Current reliability, issues, failed rules, contract violations, drift, remediation, alerts, and scheduled audits
- Executive, dataset, issue, rule, contract, drift, remediation, audit, alert, and operational reports
- CSV and PDF report exports
- Saved and scheduled reports
- Current-state and historical platform summaries

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Data processing | Pandas |
| Persistence | SQLAlchemy, SQLite |
| Migrations | Alembic |
| Frontend | HTML, CSS, vanilla JavaScript |
| Visualisation | Chart.js |
| Authentication | Server-side sessions and password hashing |
| AI integration | OpenAI API with deterministic fallback |
| Testing | Pytest, HTTPX |
| Runtime | Uvicorn |

## Architecture

```text
Browser UI
   │
   ▼
FastAPI routes and workspace-scoped dependencies
   │
   ├── Authentication and tenancy
   ├── Dataset registry and ingestion
   ├── Profiling and privacy intelligence
   ├── Quality-rule execution
   ├── Contract generation and validation
   ├── Reliability scoring
   ├── Issue lifecycle and remediation
   ├── Scheduling, alerts, and connectors
   ├── Reliability Copilot
   └── Reports and Overview aggregation
   │
   ▼
SQLAlchemy persistence and uploaded source files
   │
   ├── data/drc.db
   └── data/uploads/
```

## Project Structure

```text
DRC/
├── alembic/                 Database migrations
├── app/
│   ├── api/                 API dependencies and authentication guards
│   ├── core/                Configuration, security, and shared errors
│   ├── db/                  SQLAlchemy models, sessions, and migrations
│   ├── profiling/           Profiling inference, signals, and statistics
│   ├── static/              Single-page browser interface
│   ├── main.py              FastAPI application and routes
│   ├── auditor.py           Audit orchestration
│   ├── ingestion.py         Dataset parsing and validation
│   ├── quality_rules.py     Reusable rule engine
│   ├── contracts.py         Contract generation and validation
│   ├── scoring.py           Reliability scoring
│   ├── issue_lifecycle.py   Issue-state management
│   ├── remediation.py       Controlled correction workflow
│   ├── privacy.py           Sensitive-data detection
│   ├── versioning.py        Dataset revision lineage
│   ├── comparison.py        Audit and version comparison
│   ├── reports.py           Operational and executive reports
│   └── analyst.py           Copilot audit analysis
├── data/                    Local database and uploaded runtime data
├── documents/               Feature and implementation documentation
├── samples/                 Sample datasets and configurations
├── tests/                   Automated regression tests
├── alembic.ini
├── requirements.txt
└── README.md
```

## Local Setup

### 1. Create the environment

```powershell
cd C:\Users\user\Documents\DRC
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example configuration when present:

```powershell
Copy-Item .env.example .env
```

Typical configuration:

```env
DRC_DATABASE_PATH=data/drc.db
OPENAI_API_KEY=
OPENAI_MODEL=
```

The OpenAI key is optional. DRC continues to operate using deterministic local summaries and recommendations when no key is configured.

### 3. Apply database migrations

```powershell
python -m alembic heads
python -m alembic upgrade head
```

Current migration head:

```text
0014
```

### 4. Start the application

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Clean End-to-End Test Reset

Stop the server before clearing local state.

```powershell
Remove-Item .\data\drc.db -Force -ErrorAction SilentlyContinue
Remove-Item .\runtime\* -Recurse -Force -ErrorAction SilentlyContinue
python -m alembic upgrade head
```

This removes users, workspaces, datasets, audits, rules, contracts, alerts, reports, and Copilot sessions from the local database.

Do not delete the source code, migrations, tests, documentation, or virtual environment.

## Running Tests

Run the complete regression suite:

```powershell
python -m pytest -v
```

Run a focused area:

```powershell
python -m pytest tests/test_overview_command_centre.py -v
python -m pytest tests/test_reports.py -v
python -m pytest tests/test_reliability_copilot.py -v
python -m pytest tests/test_rules_workspace_completion.py -v
```

Check JavaScript syntax:

```powershell
node --check app/static/app.js
```

Compile Python modules:

```powershell
python -m compileall app
```

## Dataset and Audit Versioning Rules

DRC intentionally separates source revisions from audit executions.

- Importing a new dataset creates `v1`.
- Using **Import new version** creates `v2`, `v3`, and later source revisions.
- Running or rerunning an audit does not create a dataset version.
- Scheduled audits do not create dataset versions.
- Rule re-evaluation does not create dataset versions.
- Each audit retains its own run ID, timestamp, source file, and dataset-version context.

## Contract Behaviour

A generated contract combines:

1. The selected dataset schema
2. Active quality rules assigned to that dataset
3. Non-enforcing profile observations

Enforceable constraints include required fields, uniqueness, expected types, allowed values, ranges, formats, freshness, and missing thresholds.

Observed source minima, maxima, and distinct values are retained as profile context and are not automatically promoted into governance limits.

## Timezone Behaviour

Persisted timestamps are treated as UTC and converted for display using the configured workspace or application timezone. The current local testing workflow uses:

```text
Africa/Nairobi
```

Audit selectors, run details, alerts, activities, schedules, and reports should display the same local time for the same event.

## Security and Privacy

- Authentication uses server-side sessions.
- Organisations and workspaces isolate platform resources.
- Role checks protect administrative and write operations.
- Uploaded files and the local database are excluded from source control.
- Raw row-level values are not sent to an external language model by default.
- Copilot context prioritises aggregate metrics, governed metadata, findings, and approved operational context.
- Sensitive-data controls and evidence are tracked per column.

## Data Storage

Default local locations:

```text
data/drc.db
data/uploads/
```

Override the database through:

```env
DRC_DATABASE_URL=
```

or:

```env
DRC_DATABASE_PATH=data/drc.db
```

Back up the `data` directory before overlaying a replacement project build.

## Deployment

The application can run on any Python-compatible environment that supports persistent storage.

Production command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Health endpoint:

```text
GET /health
```

For production deployment:

- Use a managed relational database instead of local SQLite.
- Store uploaded files in durable object storage.
- configure secure session and application secrets.
- Restrict allowed origins and trusted hosts.
- Run migrations as part of deployment.
- Configure background execution for schedules and reports.
- Store API keys in a secret manager.
- Enable centralised logs, metrics, backups, and alerting.

## Main Workspaces

```text
Overview
Data Management
  ├── Datasets
  ├── Profiling
  └── Version history
Monitoring
  ├── Audit Workspace
  ├── Scheduled Audits
  ├── Alerts
  └── Remediation
Governance
  ├── Quality Rules
  ├── Data Contracts
  └── Privacy Intelligence
AI Assistance
  └── Reliability Copilot
Administration
  ├── Team and invitations
  ├── Workspaces
  ├── Connectors
  └── Reports
```

## Current Product Scope

DRC is suitable for:

- Product demonstrations
- Portfolio and technical case-study use
- Local or controlled pilot deployments
- Data-quality workflow evaluation
- Reliability operations prototyping
- Human-led AI orchestration experiments

Before a broad production rollout, complete external database migration, object-storage integration, background job execution, connector hardening, security review, load testing, and operational observability.

## Documentation

Detailed feature documentation is available in:

```text
documents/
```

It covers the platform foundation, authentication, workspaces, dataset management, profiling, audits, rules, contracts, scoring, issue lifecycle, privacy, remediation, versioning, drift, schedules, alerts, connectors, Reliability Copilot, reports, Overview, and UI consistency refinements.

## Production foundation

The cleaned baseline includes PostgreSQL readiness, environment validation, local/GCS object-storage interfaces, and a background-job foundation. See `documents/FEATURE_25_PRODUCTION_FOUNDATION_STEPS_1_10.md` for configuration and validation details.

## Quality gates and CI/CD

Feature 32 adds PostgreSQL-backed CI, migration validation, coverage, Playwright browser tests, security checks, container verification and a controlled Cloud Run deployment workflow. See `documents/FEATURE_32_TESTING_AND_CICD.md`.
