# Feature 32 — Testing and CI/CD

## Scope

Phase 6 establishes repeatable quality gates, browser regression coverage, immutable container builds, and a controlled Cloud Run deployment path.

## Test layers

- Python unit and API integration tests run with PostgreSQL in CI.
- Alembic upgrades are validated against a clean PostgreSQL service.
- Coverage is reported with a 70% minimum baseline.
- Playwright tests cover login-shell availability, authenticated application access, desktop/mobile rendering, and health endpoints.
- Security checks use the project secret scanner, Bandit, and pip-audit.
- Every accepted change must also produce a valid production container image.

## Workflows

- `ci.yml`: compile, lint, migrations, tests, coverage, security and image build.
- `e2e.yml`: starts PostgreSQL and DRC, waits for readiness, then runs Chromium desktop/mobile tests.
- `deploy.yml`: manual, environment-protected Cloud Run deployment using Workload Identity Federation, an immutable commit-SHA image, a migration job, candidate verification and traffic promotion.

## Local commands

```powershell
pip install -r requirements-dev.txt
python -m compileall -q app tests scripts
ruff check app scripts tests/test_ci_cd.py
pytest

npm install
npx playwright install chromium
npm run test:e2e

docker build -t drc:local .
```

## GitHub configuration

Create `staging` and `production` environments. Require reviewers for production. Configure repository or environment variables:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `CLOUD_RUN_REGION_HASH`
- `CLOUD_RUN_SERVICE`
- `ARTIFACT_REPOSITORY`

Configure secrets:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

Runtime application secrets remain in Google Secret Manager or Cloud Run configuration; they are not stored in GitHub or the image.

## Rollback

Cloud Run revisions remain immutable. Roll back by shifting traffic to the last healthy revision. Database migrations must be designed to remain backward compatible during deployment; destructive changes require a separate planned migration and backup.
