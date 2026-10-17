"""Probe Qunar mobile flight list page in headless browser; capture JSON APIs."""
import json
import sys
import asyncio
from urllib.parse import quote

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


async def main(dep_city: str, arr_city: str, date: str):
    jsons = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA, locale="zh-CN",
            viewport={"width": 390, "height": 844},
            is_mobile=True,
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()

        async def on_response(resp):
            if "flightlist" in resp.url or "lowestPrice" in resp.url:
                try:
                    data = await resp.json()
                    jsons.append((resp.url[:140], data))
                except Exception:
                    pass

        page.on("response", on_response)

        url = (f"https://m.flight.qunar.com/ncs/page/flightlist?"
               f"depCity={quote(dep_city)}&arrCity={quote(arr_city)}"
               f"&goDate={date}&from=touch_index_search&child=0&baby=0&cabinType=0")
        print(f"[i] opening {url}", file=sys.stderr)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[!] goto: {e}", file=sys.stderr)
        await page.wait_for_timeout(12000)
        title = await page.title()
        body = (await page.inner_text("body"))[:500]
        print(f"[i] title: {title}", file=sys.stderr)
        print(f"[i] body head: {body!r}", file=sys.stderr)
        await browser.close()

    print(f"\n[i] captured {len(jsons)} price-bearing JSON responses")
    for u, d in jsons[:3]:
        print("==", u)
        print(json.dumps(d, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
