"""Prototype: fetch Ctrip lowest-price calendar via headless browser.

Usage:
    python fetch_ctrip_test.py SHA BJS 2026-11-01
City codes use Ctrip pinyin codes (sha=Shanghai, bjs=Beijing, can=Guangzhou...).
The page itself calls /itinerary/api/12808/lowestPrice; we capture that JSON.
"""
import json
import os
import sys
import asyncio

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


async def fetch(dep: str, arr: str, date: str) -> dict:
    captured = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=(os.environ.get("HEADLESS", "1") == "1"),
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA, locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()

        async def on_response(resp):
            if "lowestPrice" in resp.url:
                try:
                    captured["lowest"] = await resp.json()
                except Exception:
                    pass

        page.on("response", on_response)

        url = (f"https://flights.ctrip.com/online/list/"
               f"oneway-{dep.lower()}-{arr.lower()}?depdate={date}")
        print(f"[i] opening {url}", file=sys.stderr)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[!] goto: {e}", file=sys.stderr)

        # wait for the lowestPrice API or any price text
        for _ in range(30):
            if captured.get("lowest"):
                break
            await page.wait_for_timeout(1000)

        title = await page.title()
        print(f"[i] page title: {title}", file=sys.stderr)
        if not captured.get("lowest"):
            # fallback: dump some visible price-ish text
            body = await page.inner_text("body")
            print(f"[!] no lowestPrice captured; body head:\n{body[:600]}",
                  file=sys.stderr)
        await browser.close()
    return captured


if __name__ == "__main__":
    dep, arr, date = sys.argv[1], sys.argv[2], sys.argv[3]
    result = asyncio.run(fetch(dep, arr, date))
    low = result.get("lowest")
    if low:
        print(json.dumps(low, ensure_ascii=False, indent=2)[:3000])
    else:
        print("FAILED: no data captured")
        sys.exit(1)
