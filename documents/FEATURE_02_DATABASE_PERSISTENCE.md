# Feature 02 — Database Persistence

## Purpose
Stores audits, issues, and uploaded dataset records reliably in a database instead of local JSON files.

## How it works
SQLAlchemy manages application data in SQLite and Alembic applies versioned database migrations when the application starts.
