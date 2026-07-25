from __future__ import annotations

import secrets
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.errors import error_payload
from app.services.security_audit import record_authenticated_mutation

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
CSRF_EXEMPT_PATHS = {"/auth/login", "/auth/register", "/auth/password-reset/confirm", "/auth/email-verification/confirm", "/team/invitations/accept", "/schedules/dispatch"}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id

        if settings.csrf_enabled and request.method not in SAFE_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            session_token = request.cookies.get(settings.session_cookie_name)
            if session_token:
                cookie_token = request.cookies.get(settings.csrf_cookie_name)
                header_token = request.headers.get("x-csrf-token")
                if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
                    return JSONResponse(status_code=403, content=error_payload("csrf_failed", "CSRF validation failed."))

        response = await call_next(request)
        if request.method not in SAFE_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            record_authenticated_mutation(request, response.status_code)
        if request.cookies.get(settings.session_cookie_name) and not request.cookies.get(settings.csrf_cookie_name):
            response.set_cookie(
                settings.csrf_cookie_name,
                secrets.token_urlsafe(32),
                max_age=settings.session_hours * 3600,
                secure=settings.secure_cookies,
                httponly=False,
                samesite="strict",
                path="/",
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
