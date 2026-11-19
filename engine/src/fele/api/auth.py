"""Optional password gate for the hosted demo (env DEMO_PASSWORD). Off when the variable is empty.

POST /login with the password sets an HttpOnly cookie holding an HMAC of the password (never the password itself);
every data endpoint then requires it. Comparisons are constant-time.
"""

import asyncio
import hashlib
import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from fele.config import settings

COOKIE = "fele_session"
OPEN_PATHS = frozenset({"/health", "/login", "/logout", "/info", "/docs", "/redoc", "/openapi.json", "/"})
FAILED_LOGIN_DELAY_S = 0.5  # slows down password guessing
SESSION_DAYS = 14


def _password() -> str | None:
    secret = settings().demo_password
    return secret.get_secret_value() if secret and secret.get_secret_value() else None


def protected() -> bool:
    return _password() is not None


def _token(password: str) -> str:
    return hmac.new(password.encode(), b"fele-demo-session", hashlib.sha256).hexdigest()


def authorized(request: Request) -> bool:
    password = _password()
    if password is None:
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""), _token(password))


async def login(password: str, request: Request, response: Response) -> bool:
    expected = _password()
    if expected is None:
        return True
    if not hmac.compare_digest(password.encode(), expected.encode()):
        await asyncio.sleep(FAILED_LOGIN_DELAY_S)
        return False
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        COOKIE, _token(expected), max_age=SESSION_DAYS * 86400, httponly=True, samesite="strict", secure=secure
    )
    return True


async def gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """HTTP middleware: 401 for data endpoints without a valid session when the demo is protected."""
    if request.url.path in OPEN_PATHS or authorized(request):
        return await call_next(request)
    return JSONResponse({"detail": "Login required"}, status_code=401)
