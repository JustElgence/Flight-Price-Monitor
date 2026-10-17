"""Probe a list of candidate flight pages in headless browser, dump JSON captures."""
import json
import sys
import asyncio
from urllib.parse import quote

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


async def probe(page, url, wait_ms=12000):
    jsons = []

    async def on_response(resp):
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            try:
                data = await resp.json()
                s = json.dumps(data, ensure_ascii=False)
                if "price" in s.lower() or "Price" in s:
                    jsons.append((resp.url[:140], s))
            except Exception:
                pass

    page.on("response", on_response)
    print(f"\n=== {url}", file=sys.stderr)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print(f"[!] goto: {e}", file=sys.stderr)
    await page.wait_for_timeout(wait_ms)
    title = await page.title()
    body = (await page.inner_text("body"))[:400].replace("\n", " ")
    print(f"[i] title: {title}", file=sys.stderr)
    print(f"[i] body: {body!r}", file=sys.stderr)
    page.remove_listener("response", on_response)
    return jsons


async def main(dep, arr, date):
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

        all_jsons = []
        # Tongcheng PC
        all_jsons += await probe(
            page,
            f"https://www.ly.com/flights/itinerary/oneway/{dep}-{arr}?date={date}"
            f"&from={quote('上海')}&to={quote('北京')}")
        # Tongcheng lowprice calendar
        all_jsons += await probe(
            page,
            f"https://www.ly.com/flights/lvlowprice/lowflight.html?dcity={dep}&acity={arr}")
        await browser.close()

    print(f"\n[i] total {len(all_jsons)} price JSONs")
    for u, s in all_jsons[:5]:
        print("==", u)
        print(s[:1000])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
