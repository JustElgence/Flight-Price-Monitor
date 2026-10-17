"""Final prototype: Tongcheng (ly.com) daily lowest-price calendar extractor.

Usage:
    python fetch_ly_price.py SHA BJS 2026-11-01
Returns JSON: {"dep","arr","date","calendar":[{date,price},...]}
The calendar strip on the PC list page is server-rendered -> parse DOM text.
"""
import json
import re
import sys
import asyncio
from datetime import date as _date

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
PRICE_RE = re.compile(r"(\d{2}-\d{2})\s*周[一二三四五六日]\s*[¥¥]\s*(\d+)")


async def fetch_calendar(dep: str, arr: str, date: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(user_agent=UA, locale="zh-CN",
                                        viewport={"width": 1440, "height": 900})
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()
        url = (f"https://www.ly.com/flights/itinerary/oneway/{dep}-{arr}"
               f"?date={date}&dep={dep}&arr={arr}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(8000)
        body = await page.inner_text("body")
        await browser.close()

    today = _date.today()
    items = []
    for m in PRICE_RE.finditer(body):
        mm, dd, price = m.group(1)[:2], m.group(1)[3:5], int(m.group(2))
        year = today.year + (1 if (int(mm), int(dd)) < (today.month, today.day) else 0)
        try:
            items.append({"date": f"{year}-{mm}-{dd}", "price": price})
        except ValueError:
            continue
    return {"dep": dep, "arr": arr, "query_date": date, "calendar": items}


if __name__ == "__main__":
    dep, arr, date = sys.argv[1], sys.argv[2], sys.argv[3]
    data = asyncio.run(fetch_calendar(dep, arr, date))
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if not data["calendar"]:
        sys.exit(1)
