"""IM notification. Channels: wecom / dingtalk / qmsg(QQ) / onebot(QQ) / generic."""
import json

import httpx

from .db import get_db

DEFAULTS = {"channel": None, "webhook_url": None,
            "token": None, "target_type": None, "target_id": None}


def _plain(content: str) -> str:
    """Strip markdown syntax for plain-text channels (QQ)."""
    import re
    s = content.replace("**", "").replace("> ", "").replace("### ", "")
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s


def _wecom_markdown(webhook: str, content: str):
    return httpx.post(webhook, json={"msgtype": "markdown",
                                     "markdown": {"content": content}}, timeout=15)


def _dingtalk_markdown(webhook: str, title: str, content: str):
    return httpx.post(webhook, json={"msgtype": "markdown",
                                     "markdown": {"title": title, "text": content}},
                      timeout=15)


def _generic(webhook: str, title: str, content: str):
    return httpx.post(webhook, json={"title": title, "content": content}, timeout=15)


def _qmsg(cfg: dict, content: str):
    """Qmsg酱 3.0 (QQ official bot relay). webhook_url = KEY, target_id = QQ号."""
    key, qq = cfg.get("webhook_url", "").strip(), cfg.get("target_id")
    url = f"https://qmsg.zendee.cn/v3/jsend/{key}"
    payload = {"msg": _plain(content)}
    if qq:
        payload["qq"] = str(qq).strip()
    return httpx.post(url, json=payload, timeout=15)


def _onebot(cfg: dict, content: str):
    """OneBot v11 HTTP (NapCat 等). webhook_url=base, token=access_token,
    target_type=private|group, target_id=QQ号/群号."""
    base = cfg.get("webhook_url", "").rstrip("/")
    endpoint = "/send_group_msg" if cfg.get("target_type") == "group" \
        else "/send_private_msg"
    key = "group_id" if cfg.get("target_type") == "group" else "user_id"
    headers = {"Content-Type": "application/json"}
    if cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"
    payload = {key: int(cfg["target_id"]),
               "message": _plain(content)}
    return httpx.post(base + endpoint, json=payload, headers=headers, timeout=15)


def get_notify_config() -> dict:
    with get_db() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key='notify'").fetchone()
    if not row:
        return dict(DEFAULTS)
    cfg = json.loads(row["value"])
    return {**DEFAULTS, **cfg}


def set_notify_config(cfg: dict):
    data = {k: cfg.get(k) for k in DEFAULTS}
    with get_db() as db:
        db.execute(
            "INSERT INTO settings(key,value) VALUES('notify',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(data, ensure_ascii=False),))


def send(title: str, content: str, cfg: dict | None = None) -> tuple[bool, str]:
    """Send notification. Returns (ok, message)."""
    cfg = cfg or get_notify_config()
    channel = cfg.get("channel")
    if not channel or not cfg.get("webhook_url"):
        return False, "通知渠道未配置"
    try:
        if channel == "wecom":
            r = _wecom_markdown(cfg["webhook_url"], content)
        elif channel == "dingtalk":
            r = _dingtalk_markdown(cfg["webhook_url"], title, content)
        elif channel == "qmsg":
            r = _qmsg(cfg, content)
        elif channel == "onebot":
            r = _onebot(cfg, content)
        else:
            r = _generic(cfg["webhook_url"], title, content)
        ok = 200 <= r.status_code < 300
        body = r.text[:200]
        return ok, f"HTTP {r.status_code}: {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
