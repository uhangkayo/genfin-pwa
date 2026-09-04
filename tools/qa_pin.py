#!/usr/bin/env python3
"""Ukur geometri layar PIN + layar utama di viewport mobile."""
import asyncio, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

async def run():
    subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, w, h in [('iphone14', 390, 844), ('iphoneSE', 375, 667)]:
            ctx = await b.new_context(viewport={'width': w, 'height': h},
                                      device_scale_factor=3, is_mobile=True, has_touch=True)
            page = await ctx.new_page()
            await page.goto(APP, wait_until='domcontentloaded')
            await page.wait_for_selector('#gf-f-ak', timeout=8000)
            await page.fill('#gf-f-ak', KEY)
            await page.click('#gf-ok')
            await page.wait_for_selector('#gf-f-p1', timeout=8000)
            await page.fill('#gf-f-p1', PASS)
            await page.fill('#gf-f-p2', PASS)
            await page.click('#gf-ok')
            await page.wait_for_timeout(2500)
            # layar PIN
            m = await page.evaluate('''() => {
                const ov = document.querySelector('div[style*="z-index:60"]');
                if (!ov) return {pin: false};
                const cs = getComputedStyle(ov);
                const lock = ov.querySelector('div');
                const grid = ov.querySelector('div[style*="grid-template-columns"]');
                const kids = [...ov.children];
                const first = kids[0].getBoundingClientRect();
                const last = kids[kids.length-1].getBoundingClientRect();
                const g = grid ? grid.getBoundingClientRect() : null;
                return {
                    pin: true,
                    ovH: ov.scrollHeight, ovClientH: ov.clientHeight, ovScrollTop: ov.scrollTop,
                    display: cs.display, align: cs.alignItems, justify: cs.justifyContent,
                    topGap: Math.round(first.top),
                    bottomGap: Math.round(ov.clientHeight - last.bottom),
                    gridTop: g ? Math.round(g.top) : null,
                    gridBottom: g ? Math.round(g.bottom) : null,
                    contentH: Math.round(last.bottom - first.top),
                    vh: window.innerHeight,
                };
            }''')
            print(f'=== {name} ({w}x{h}) PIN ===')
            for k, v in m.items(): print(f'  {k}: {v}')
            await page.screenshot(path=f'/tmp/gf_{name}_pin.png')
            # isi PIN supaya masuk app utama
            for d in '1234':
                await page.keyboard.press(d)
                await page.wait_for_timeout(120)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(2000)
            m2 = await page.evaluate('''() => {
                const nav = document.querySelector('nav');
                const main = document.querySelector('main');
                const hero = document.querySelector('main section div');
                return {
                    vh: window.innerHeight, vw: window.innerWidth,
                    docH: document.documentElement.scrollHeight,
                    navBottom: nav ? Math.round(nav.getBoundingClientRect().bottom) : null,
                    mainBottom: main ? Math.round(main.getBoundingClientRect().bottom) : null,
                    heroTop: hero ? Math.round(hero.getBoundingClientRect().top) : null,
                };
            }''')
            print(f'=== {name} HOME ===')
            for k, v in m2.items(): print(f'  {k}: {v}')
            await page.screenshot(path=f'/tmp/gf_{name}_app.png')
            await ctx.close()
        await b.close()

asyncio.run(run())
print('SELESAI')
