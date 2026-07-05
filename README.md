# Data Reliability Copilot

Data Reliability Copilot is an LLM-ready data quality, remediation, and governance app. It accepts tabular datasets, profiles their structure, detects quality issues with deterministic rules, scores dataset health, generates remediation actions, creates reusable data contracts, compares audit versions, and produces business-friendly recommendations.

## MVP Capabilities

- Upload or audit CSV files.
- Profile columns, types, missingness, uniqueness, and sample values.
- Detect completeness, uniqueness, validity, consistency, anomaly, integrity, privacy, and timeliness issues.
- Compute transparent quality scores.
- Generate an executive summary without sending raw data to an LLM.
- Persist audits and uploaded source files locally.
- Reopen saved audits from the dashboard.
- Filter issues by severity and category.
- Track issue workflow status.
- Generate remediation actions and draft Pandas cleaning code.
- Generate reusable data contracts.
- Compare audits across dataset versions.
- Assess ML readiness.
- Ask an analyst-style question about the audit.
- Export Markdown audit reports.
- Serve a tabbed operational workbench from the backend.

## Project Structure

```text
app/
  main.py              FastAPI app and routes
  auditor.py           End-to-end audit orchestration
  ingestion.py         CSV parsing and validation
  profiler.py          Dataset and column profiling
  rules.py             Data quality checks
  scoring.py           Quality scoring model
  summaries.py         LLM-ready summary generation
  reports.py           Markdown report generation
  schemas.py           Pydantic response models
  storage.py           File-backed persistence
  remediation.py       Fix actions and draft cleaning scripts
  contracts.py         Data contract generation
  comparison.py        Audit-to-audit comparison
  ml_readiness.py      ML training readiness scoring
  analyst.py           Analyst-style audit Q&A
  static/              Browser dashboard
samples/
  customers_dirty.csv  Demo dataset
tests/
  test_auditor.py      Core behavior tests
```

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` and upload `samples/customers_dirty.csv`.

For LLM-generated summaries, copy `.env.example` to `.env`, set `OPENAI_API_KEY`, and optionally set `OPENAI_MODEL`. Without an API key, the app uses the deterministic local summary so demos and tests still run offline.

## Deployment

The project includes a Render Blueprint in `render.yaml`.

Production start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The `/health` endpoint is used for deployment health checks. Set `OPENAI_API_KEY` as a secret environment variable only if LLM-generated summaries are needed in production.

## API

- `GET /health`
- `GET /audits`
- `POST /audits/upload`
- `POST /audits/sample`
- `POST /audits/sample/configured`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/issues`
- `PATCH /audits/{audit_id}/issues/{issue_id}`
- `GET /audits/{audit_id}/report`
- `GET /audits/{audit_id}/report.md`
- `GET /audits/{audit_id}/remediation`
- `GET /audits/{audit_id}/contract`
- `GET /audits/{audit_id}/ml-readiness`
- `GET /audits/compare/{baseline_audit_id}/{candidate_audit_id}`
- `POST /audits/{audit_id}/analyst`
- `POST /audits/{audit_id}/summary/regenerate`

## Configurable Rules

Uploads accept an optional `rules_json` form field. The dashboard includes a textarea for this field.

Example:

```json
{
  "required_columns": ["customer_id", "email", "status"],
  "unique_columns": ["customer_id"],
  "expected_types": {
    "signup_date": "datetime",
    "monthly_spend": "numeric"
  },
  "allowed_values": {
    "status": ["Active", "Inactive"]
  },
  "numeric_ranges": {
    "monthly_spend": { "min": 0, "max": 1000 }
  },
  "date_ranges": {
    "signup_date": { "min": "2020-01-01", "max": "today" }
  },
  "stale_after_days": {
    "updated_at": 365
  }
}
```

## Privacy Posture

The audit engine is deterministic-first. The summary layer sends only aggregate metrics, issue records, and column-level context to the LLM. Row examples are excluded from the LLM context by default.

## Persistence

Audits are saved as JSON files in `data/audits/`, so results survive server restarts. Uploaded CSVs are saved in `data/uploads/`. Both folders are ignored by Git because they may contain dataset-derived details.

## LLM Contract

When `OPENAI_API_KEY` is configured, the app requests a strict JSON-schema response and validates it with `LlmAuditSummary`. Invalid or unavailable model responses fall back to the local rule-based summary.

## Roadmap

- Excel ingestion
- Persistent database storage
- PDF report export
- Configurable custom rules
- OpenAI structured-output summaries
- Database and Google Sheets connectors
- Scheduled re-audits and schema drift monitoring
