"""Tongcheng (ly.com) lowest-price calendar + flight list fetcher.

Runs Playwright headless Chromium in a worker thread; returns:
{
  "dep","arr","query_date",
  "target_price": float|None,     # lowest price for the task's date
  "calendar": [{"date","price"}], # forward calendar from SSR page
  "flights": [                    # flight list for query_date
    {"airline","flight_no","plane","dep_time","dep_airport",
     "duration","arr_time","arr_airport","price","cabin"}
  ],
}
"""
import asyncio
import json
import re
import threading
from datetime import date as _date

from playwright.sync_api import sync_playwright

from .config import BASE_DIR

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PRICE_RE = re.compile(r"(\d{2}-\d{2})\s*周[一二三四五六日]\s*[¥￥]\s*(\d+)")
FLIGHT_RE = re.compile(
    r"([\u4e00-\u9fa5]{2,10})([A-Z0-9]{2}\d{3,4})\n+"
    r"([^\n]+)\n+"
    r"(\d{1,2}:\d{2})\n+([^\n]+)\n+(\d+h\d{2}m)\n+"
    r"(\d{1,2}:\d{2})\n+([^\n]+)\n+"
    r"[¥￥](\d+)起\n+([^\n]+)")
PRICE_QI_RE = re.compile(r"[¥￥]\d+起")  # marker: flight list rendered

_lock = threading.Lock()  # serialize browser launches


def _parse_flights(body: str) -> list[dict]:
    flights = []
    for m in FLIGHT_RE.finditer(body):
        airline, fno, plane, dep_t, dep_ap, dur, arr_t, arr_ap, price, cabin = \
            m.groups()
        flights.append({
            "airline": airline, "flight_no": fno, "plane": plane.strip(),
            "dep_time": dep_t, "dep_airport": dep_ap.strip(),
            "duration": dur, "arr_time": arr_t, "arr_airport": arr_ap.strip(),
            "price": int(price), "cabin": cabin.strip(),
        })
    return flights


def _crawl(dep: str, arr: str, query_date: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        try:
            ctx = browser.new_context(user_agent=UA, locale="zh-CN",
                                      viewport={"width": 1440, "height": 900})
            ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            page = ctx.new_page()
            url = (f"https://www.ly.com/flights/itinerary/oneway/{dep}-{arr}"
                   f"?date={query_date}&dep={dep}&arr={arr}")
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(6000)
            # scroll to trigger lazy-loaded flight list
            body = page.inner_text("body")
            for _ in range(12):
                if PRICE_QI_RE.search(body):
                    break
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1500)
                body = page.inner_text("body")
            page.wait_for_timeout(2000)
            body = page.inner_text("body")
        finally:
            browser.close()

    today = _date.today()
    items = []
    for m in PRICE_RE.finditer(body):
        mm, dd, price = m.group(1)[:2], m.group(1)[3:5], int(m.group(2))
        year = today.year + (1 if (int(mm), int(dd)) < (today.month, today.day) else 0)
        try:
            d = _date(year, int(mm), int(dd)).isoformat()
        except ValueError:
            continue
        items.append({"date": d, "price": price})

    flights = _parse_flights(body)
    target_price = next((it["price"] for it in items if it["date"] == query_date), None)
    return {"dep": dep, "arr": arr, "query_date": query_date,
            "target_price": target_price, "calendar": items,
            "flights": flights}


def crawl(dep: str, arr: str, query_date: str) -> dict:
    """Thread-safe crawl; raises RuntimeError on empty result."""
    with _lock:
        data = _crawl(dep, arr, query_date)
    if not data["calendar"]:
        raise RuntimeError("empty calendar (page layout changed or blocked)")
    return data


async def crawl_async(dep: str, arr: str, query_date: str) -> dict:
    return await asyncio.to_thread(crawl, dep, arr, query_date)
