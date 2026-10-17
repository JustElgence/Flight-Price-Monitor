"""Account + password login for FlyMon (single user).

Configure via env:
  FLYMON_USERNAME  (default: admin)
  FLYMON_PASSWORD  (required to enable auth; empty disables auth)

Session cookie = HMAC of username+password, so sessions survive restarts
as long as the credentials are unchanged.
"""
import hashlib
import hmac
import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .config import BASE_DIR

COOKIE = "flymon_session"

router = APIRouter()


def _username() -> str:
    return os.environ.get("FLYMON_USERNAME", "admin")


def _password() -> str:
    return os.environ.get("FLYMON_PASSWORD", "")


def _session_token(username: str, password: str) -> str:
    return hmac.new(b"flymon-session-v1",
                    f"{username}:{password}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def is_authed(request: Request) -> bool:
    pwd = _password()
    if not pwd:  # auth disabled when no password configured
        return True
    return hmac.compare_digest(request.cookies.get(COOKIE, ""),
                               _session_token(_username(), pwd))


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
    user = (body.get("username") or "").strip()
    given = (body.get("password") or "").strip()
    if not pwd:
        return JSONResponse({"ok": True, "msg": "未启用认证"})
    if user == _username() and given and hmac.compare_digest(given, pwd):
        resp = JSONResponse({"ok": True})
        resp.set_cookie(COOKIE, _session_token(user, given), max_age=30 * 86400,
                        httponly=True, samesite="lax")
        return resp
    return JSONResponse({"ok": False, "msg": "账号或密码错误"}, status_code=401)
