"""Authentication middleware for OpenShift OAuth Proxy integration.

When DFD_AUTH_ENABLED is set, the OAuth proxy handles login and sets
X-Forwarded-User on forwarded requests.  In local dev mode (no proxy),
all requests are allowed through as "anonymous".
"""

from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/health"}

AUTH_ENABLED = os.environ.get(
    "DFD_AUTH_ENABLED", ""
).lower() in ("true", "1", "yes")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            request.state.user = None
            return await call_next(request)

        if AUTH_ENABLED:
            user = request.headers.get("X-Forwarded-User")
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated"},
                )
            request.state.user = user
        else:
            request.state.user = "anonymous"

        return await call_next(request)
