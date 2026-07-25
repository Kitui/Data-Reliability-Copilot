from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, details: object | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details  # type: ignore[index]
    return payload


async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_payload("internal_error", "An unexpected error occurred."),
    )
