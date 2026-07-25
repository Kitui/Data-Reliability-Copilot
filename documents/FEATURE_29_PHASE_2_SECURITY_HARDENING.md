# Feature 29 — Phase 2 Security Hardening

## Scope

This release completes the locked Phase 2 security work:

- Login throttling, failed-attempt tracking and temporary account lockout
- Strong password policy
- Expiring sessions, session inventory and revocation
- Password-reset and optional email-verification token workflows
- Double-submit CSRF protection for cookie-authenticated mutations
- Secure cookie controls, trusted hosts, explicit CORS and security headers
- Safe generic server errors and request IDs
- Workspace-scoped administrative audit log
- Automated mutation logging with secret redaction
- Tenant-isolation regression coverage
- Dependency, static-security and secret-pattern CI checks

## Production settings

Set secure cookies, CSRF, explicit allowed hosts/origins and keep development token exposure disabled. Password-reset and verification endpoints intentionally do not reveal whether an email exists. A real email delivery provider remains a later integration; development tokens can only be exposed outside production with `DRC_EXPOSE_DEV_TOKENS=true`.

## Migration

Run `alembic upgrade head` to apply revision `0018_security_hardening`.
