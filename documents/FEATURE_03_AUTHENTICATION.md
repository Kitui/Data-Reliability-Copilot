# Feature 03 — Authentication

## Purpose
Protects the application and gives each user a secure identity.

## How it works
Users sign in with a hashed password. The server creates an expiring session and sends an HTTP-only cookie used to authorize protected requests.
