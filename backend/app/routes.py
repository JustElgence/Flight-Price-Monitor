"""REST API routes."""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import fetcher, notifier
from .config import CITY_CODES
from .db import get_db, now_str
from .scheduler import crawl_task

router = APIRouter(prefix="/api")


class TaskIn(BaseModel):
    dep: str
    arr: str
    date: str
    threshold: float | None = None
    interval_min: int = 480
    flight_no: str | None = None   # 指定航班号（如 MU6345），留空监控整日最低


class TaskPatch(BaseModel):
    threshold: float | None = None
    interval_min: int | None = None
    enabled: bool | None = None
    flight_no: str | None = None


class NotifyIn(BaseModel):
    channel: str  # wecom | dingtalk | qmsg | onebot | generic
    webhook_url: str
    token: str | None = None
    target_type: str | None = None   # onebot: private | group
    target_id: str | None = None     # onebot: QQ号/群号; qmsg: QQ号


def _resolve_city(s: str) -> str:
    s = s.strip()
    if len(s) == 3 and s.isalpha():
        return s.upper()
    for name, code in CITY_CODES.items():
        if name in s or s == code:
            return code
    raise HTTPException(400, f"无法识别城市: {s}（可用城市见 /api/cities）")


@router.get("/cities")
def cities():
    return [{"name": k, "code": v} for k, v in CITY_CODES.items()]


@router.get("/tasks")
def list_tasks():
    with get_db() as db:
        rows = db.execute("SELECT * FROM monitor_task ORDER BY id").fetchall()
        out = []
        for t in rows:
            d = dict(t)
            pr = db.execute(
                "SELECT min_price, captured_at FROM price_record "
                "WHERE task_id=? ORDER BY captured_at DESC LIMIT 1",
                (t["id"],)).fetchone()
            d["latest_price"] = pr["min_price"] if pr else None
            d["latest_captured_at"] = pr["captured_at"] if pr else None
            out.append(d)
    return out


@router.post("/tasks")
async def create_task(body: TaskIn):
    dep, arr = _resolve_city(body.dep), _resolve_city(body.arr)
    if dep == arr:
        raise HTTPException(400, "出发地与目的地相同")
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "日期格式应为 YYYY-MM-DD")
    flight_no = (body.flight_no or "").strip().upper() or None
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO monitor_task(dep,arr,date,threshold,interval_min,flight_no) "
            "VALUES(?,?,?,?,?,?)",
            (dep, arr, body.date, body.threshold, max(60, body.interval_min),
             flight_no))
        task_id = cur.lastrowid
    res = await crawl_task(task_id)
    return {"id": task_id, "first_crawl": res}


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch):
    with get_db() as db:
        t = db.execute("SELECT * FROM monitor_task WHERE id=?", (task_id,)).fetchone()
        if not t:
            raise HTTPException(404, "任务不存在")
        if body.threshold is not None:
            db.execute("UPDATE monitor_task SET threshold=? WHERE id=?",
                       (body.threshold, task_id))
        if body.interval_min is not None:
            db.execute("UPDATE monitor_task SET interval_min=? WHERE id=?",
                       (max(60, body.interval_min), task_id))
        if body.enabled is not None:
            db.execute("UPDATE monitor_task SET enabled=? WHERE id=?",
                       (1 if body.enabled else 0, task_id))
        if body.flight_no is not None:
            db.execute("UPDATE monitor_task SET flight_no=? WHERE id=?",
                       (body.flight_no.strip().upper() or None, task_id))
        return dict(db.execute("SELECT * FROM monitor_task WHERE id=?",
                               (task_id,)).fetchone())


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    with get_db() as db:
        cur = db.execute("DELETE FROM monitor_task WHERE id=?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "任务不存在")
        db.execute("DELETE FROM price_record WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM calendar_snapshot WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM alert_log WHERE task_id=?", (task_id,))
    return {"deleted": task_id}


@router.post("/tasks/{task_id}/refresh")
async def refresh_task(task_id: int):
    return await crawl_task(task_id)


@router.get("/tasks/{task_id}/history")
def history(task_id: int, days: int = 30):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        rows = db.execute(
            "SELECT captured_at, min_price FROM price_record "
            "WHERE task_id=? AND captured_at>=? ORDER BY captured_at",
            (task_id, since)).fetchall()
    return [{"captured_at": r["captured_at"], "price": r["min_price"]} for r in rows]


@router.get("/tasks/{task_id}/latest")
def latest(task_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT captured_at, data FROM calendar_snapshot "
            "WHERE task_id=? ORDER BY captured_at DESC LIMIT 1",
            (task_id,)).fetchone()
    if not row:
        return {"captured_at": None, "calendar": [], "flights": []}
    data = json.loads(row["data"])
    flights = sorted(data.get("flights", []), key=lambda x: x["price"])
    return {"captured_at": row["captured_at"],
            "calendar": data.get("calendar", []),
            "flights": flights}


@router.get("/tasks/{task_id}/alerts")
def alerts(task_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM alert_log WHERE task_id=? ORDER BY notified_at DESC "
            "LIMIT 20", (task_id,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/settings/notify")
def get_notify():
    return notifier.get_notify_config()


@router.post("/settings/notify")
def set_notify(body: NotifyIn):
    if body.channel not in ("wecom", "dingtalk", "qmsg", "onebot", "generic"):
        raise HTTPException(400, "channel 须为 wecom/dingtalk/qmsg/onebot/generic")
    notifier.set_notify_config({
        "channel": body.channel, "webhook_url": body.webhook_url,
        "token": body.token, "target_type": body.target_type,
        "target_id": body.target_id})
    return {"ok": True}


@router.post("/settings/notify/test")
def test_notify(body: NotifyIn | None = None):
    if body and body.webhook_url:
        cfg = {"channel": body.channel, "webhook_url": body.webhook_url,
               "token": body.token, "target_type": body.target_type,
               "target_id": body.target_id}
    else:
        cfg = None
    ok, msg = notifier.send(
        "FlyMon 测试消息",
        "✈️ **FlyMon 测试**\n> 通知渠道配置成功！", cfg)
    return {"ok": ok, "msg": msg}
