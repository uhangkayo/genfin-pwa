#!/usr/bin/env python3
"""Debug alur pasca-login: poll state tiap 500ms + console."""
import asyncio, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

async def run():
    subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844},
                                  device_scale_factor=3, is_mobile=True, has_touch=True)
        page = await ctx.new_page()
        page.on('console', lambda m: print(f'[console.{m.type}] {m.text[:150]}'))
        page.on('pageerror', lambda e: print(f'[pageerror] {str(e)[:200]}'))
        await page.goto(APP, wait_until='domcontentloaded')
        await page.wait_for_selector('#gf-f-ak', timeout=8000)
        await page.fill('#gf-f-ak', KEY)
        await page.click('#gf-ok')
        await page.wait_for_selector('#gf-f-p1', timeout=8000)
        await page.fill('#gf-f-p1', PASS)
        await page.fill('#gf-f-p2', PASS)
        await page.click('#gf-ok')
        for i in range(30):
            await page.wait_for_timeout(500)
            st = await page.evaluate('''() => ({
                gate: !!document.querySelector('#gf-gate'),
                h1: document.querySelector('#gf-gate h1') ? document.querySelector('#gf-gate h1').textContent : null,
                pin: !!document.querySelector('div[style*="z-index:60"]'),
                pinTitle: document.querySelector('div[style*="z-index:60"] h2') ? document.querySelector('div[style*="z-index:60"] h2').textContent : null,
                hero: !!document.querySelector('main'),
                docH: document.documentElement.scrollHeight,
            })''')
            print(f't={(i+1)*0.5:.1f}s {st}')
            if not st['gate'] and (st['pin'] or st['hero']):
                # tunggu stabilisasi 2s lalu satu snapshot lagi
                await page.wait_for_timeout(2000)
                st2 = await page.evaluate('''() => ({
                    pin: !!document.querySelector('div[style*="z-index:60"]'),
                    docH: document.documentElement.scrollHeight,
                })''')
                print(f'STABIL: {st2}')
                await page.screenshot(path='/tmp/gf_dbg_after.png')
                break
        await ctx.close(); await b.close()

asyncio.run(run())
print('SELESAI')
