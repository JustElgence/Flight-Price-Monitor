"""Simple password login for FlyMon (single user).

Set FLYMON_PASSWORD env to enable; session cookie = HMAC of the password.
Sessions stay valid across restarts as long as the password is unchanged.
"""
import hashlib
import hmac
import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .config import BASE_DIR

COOKIE = "flymon_session"

router = APIRouter()


def _password() -> str:
    return os.environ.get("FLYMON_PASSWORD", "")


def _session_token(password: str) -> str:
    return hmac.new(b"flymon-session-v1", password.encode(),
                    hashlib.sha256).hexdigest()[:32]


def is_authed(request: Request) -> bool:
    pwd = _password()
    if not pwd:  # auth disabled when no password configured
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""),
                               _session_token(pwd))


def guard(request: Request):
    """Return a redirect/401 response when not authenticated, else None."""
    path = request.url.path
    if path in ("/login", "/api/login") or path.startswith("/vendor"):
        return None  # login page & static assets stay open
    if is_authed(request):
        return None
    if path.startswith("/api/"):
        return JSONResponse({"detail": "未登录"}, status_code=401)
    return RedirectResponse("/login", status_code=302)


@router.get("/login")
def login_page():
    return FileResponse(BASE_DIR.parent / "frontend" / "login.html")


@router.post("/api/login")
async def do_login(request: Request):
    pwd = _password()
    try:
        body = await request.json()
    except Exception:
        body = {}
    given = (body.get("password") or "").strip()
    if not pwd:
        return JSONResponse({"ok": True, "msg": "未启用口令"})
    if given and hmac.compare_digest(given, pwd):
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, _session_token(pwd), max_age=30 * 86400,
                        httponly=True, samesite="lax")
        return resp
    return JSONResponse({"ok": False, "msg": "口令错误"}, status_code=401)
