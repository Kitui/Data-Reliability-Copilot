# Feature 29 Installation

1. Preserve your existing `.env` and GCP service-account JSON outside the repository.
2. Replace the current DRC project files with this package.
3. Add the Phase 2 environment settings from `.env.example`.
4. Run `alembic upgrade head`.
5. Start with `uvicorn app.main:app --reload --env-file .env`.

For local browser use, keep `DRC_ALLOWED_HOSTS=localhost,127.0.0.1,testserver`. In production, use only the real application hostname, enable secure cookies and keep CSRF enabled.

Password-reset and email-verification tokens are stored hashed. This release provides the secure token lifecycle and APIs; actual email delivery requires a later mail-provider integration. For local-only workflow testing, `DRC_EXPOSE_DEV_TOKENS=true` may be used, but it is rejected in production.
