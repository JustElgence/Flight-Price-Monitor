"""APScheduler: periodic crawl of due tasks + threshold alert with cooldown."""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import fetcher, notifier
from .config import ALERT_COOLDOWN_HOURS, SCHED_TICK_SECONDS, city_name
from .db import get_db, now_str

log = logging.getLogger("flymon.scheduler")
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


def _recently_alerted(db, task_id: int, cooldown_hours: int) -> bool:
    since = (datetime.now() - timedelta(hours=cooldown_hours)) \
        .strftime("%Y-%m-%d %H:%M:%S")
    row = db.execute(
        "SELECT 1 FROM alert_log WHERE task_id=? AND notified_at>=? LIMIT 1",
        (task_id, since)).fetchone()
    return row is not None


def _resolve_price(task, data: dict) -> tuple[float | None, str | None]:
    """Decide tracked price & flight for a task.

    flight_no set -> price of that flight (None if not on sale this round);
    otherwise -> lowest of target date, with cheapest flight as detail.
    """
    target_no = (task["flight_no"] or "").strip().upper()
    flights = data.get("flights") or []
    if target_no:
        f = next((x for x in flights
                  if x["flight_no"].upper().startswith(target_no)), None)
        return (f["price"], f["flight_no"]) if f else (None, target_no)
    cheapest = min(flights, key=lambda x: x["price"]) if flights else None
    return data.get("target_price"), cheapest["flight_no"] if cheapest else None


def _fmt_msg(task, data: dict, price, flight_no) -> str:
    dep, arr, d = city_name(task["dep"]), city_name(task["arr"]), task["date"]
    flight_line = f"\n> 航班：**{flight_no}**" if flight_no else ""
    if task["flight_no"]:
        head = f"✈️ **降价提醒** {dep}→{arr} {d}（指定航班）"
    else:
        head = f"✈️ **降价提醒** {dep}→{arr} {d}"
    cal = {it["date"]: it["price"] for it in data["calendar"]}
    lo = min(cal.items(), key=lambda kv: kv[1]) if cal else (None, None)
    return (f"{head}\n"
            f"> 当前**¥{price}**（阈值 ¥{task['threshold']}）{flight_line}\n"
            f"> 未来最低：{lo[0]} ¥{lo[1]}\n"
            f"> 抓取时间：{now_str()}")


async def crawl_task(task_id: int) -> dict:
    """Crawl one task, persist records, maybe alert. Returns summary."""
    with get_db() as db:
        task = db.execute("SELECT * FROM monitor_task WHERE id=?", (task_id,)).fetchone()
    if not task:
        return {"ok": False, "msg": "task not found"}

    try:
        data = await fetcher.crawl_async(task["dep"], task["arr"], task["date"])
    except Exception as e:
        log.warning("crawl task %s failed: %s", task_id, e)
        return {"ok": False, "msg": str(e)}

    ts = now_str()
    price, flight_no = _resolve_price(task, data)
    with get_db() as db:
        db.execute(
            "INSERT INTO price_record(task_id,captured_at,target_date,min_price,"
            "flight_no) VALUES(?,?,?,?,?)",
            (task_id, ts, task["date"], price, flight_no))
        db.execute(
            "INSERT INTO calendar_snapshot(task_id,captured_at,data) VALUES(?,?,?)",
            (task_id, ts, _json_dumps(data)))
        db.execute("UPDATE monitor_task SET last_crawled_at=? WHERE id=?",
                   (ts, task_id))

        alerted = False
        threshold = task["threshold"]
        if threshold is not None and price is not None and price <= threshold \
                and task["enabled"] \
                and not _recently_alerted(db, task_id, ALERT_COOLDOWN_HOURS):
            cfg = notifier.get_notify_config()
            ok, msg = notifier.send(
                f"机票降价提醒 {city_name(task['dep'])}→{city_name(task['arr'])}",
                _fmt_msg(task, data, price, flight_no), cfg)
            db.execute(
                "INSERT INTO alert_log(task_id,price,notified_at,channel) "
                "VALUES(?,?,?,?)",
                (task_id, price, ts, cfg.get("channel") or "none"))
            alerted = ok
            log.info("alert task %s: %s %s", task_id, ok, msg)

    return {"ok": True, "price": price, "flight_no": flight_no,
            "flights": len(data.get("flights") or []),
            "count": len(data["calendar"]), "alerted": alerted}


async def crawl_due_tasks():
    with get_db() as db:
        rows = db.execute(
            "SELECT id FROM monitor_task WHERE enabled=1").fetchall()
    for r in rows:
        with get_db() as db:
            t = db.execute(
                "SELECT last_crawled_at, interval_min FROM monitor_task WHERE id=?",
                (r["id"],)).fetchone()
        if not t:
            continue
        due = True
        if t["last_crawled_at"]:
            last = datetime.strptime(t["last_crawled_at"], "%Y-%m-%d %H:%M:%S")
            due = datetime.now() - last >= timedelta(minutes=t["interval_min"])
        if due:
            res = await crawl_task(r["id"])
            log.info("crawl task %s -> %s", r["id"], res)


def _json_dumps(data) -> str:
    import json
    return json.dumps(data, ensure_ascii=False)


def start_scheduler():
    scheduler.add_job(crawl_due_tasks, "interval",
                      seconds=SCHED_TICK_SECONDS, id="crawl_tick",
                      max_instances=1, coalesce=True)
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
