#!/usr/bin/env python3
"""Ukur presisi geometri overlay PIN + home (selector benar)."""
import asyncio, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

async def run():
    subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, w, h in [('iphone14', 390, 844), ('iphoneSE', 375, 667), ('promax', 430, 932)]:
            subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
            ctx = await b.new_context(viewport={'width': w, 'height': h},
                                      device_scale_factor=3, is_mobile=True, has_touch=True)
            page = await ctx.new_page()
            await page.goto(APP, wait_until='domcontentloaded')
            await page.wait_for_selector('#gf-f-ak', timeout=8000)
            await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
            await page.wait_for_selector('#gf-f-p1', timeout=8000)
            await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
            await page.wait_for_timeout(3500)
            m = await page.evaluate('''() => {
                const h2s = [...document.querySelectorAll('h2')];
                const h2 = h2s.find(x => x.textContent.includes('PIN'));
                if (!h2) return {pin: false};
                const ov = h2.closest('div');
                // naik sampai elemen fixed
                let el = h2;
                while (el && getComputedStyle(el).position !== 'fixed') el = el.parentElement;
                const ov2 = el || ov;
                const r = ov2.getBoundingClientRect();
                const kids = [...ov2.children].filter(c => c.getBoundingClientRect().height > 0);
                const first = kids[0].getBoundingClientRect();
                const last = kids[kids.length - 1].getBoundingClientRect();
                const grid = [...ov2.querySelectorAll('div')].find(d => getComputedStyle(d).display === 'grid');
                const g = grid ? grid.getBoundingClientRect() : null;
                return {
                    pin: true,
                    ovTop: Math.round(r.top), ovH: Math.round(r.height),
                    ovScrollH: ov2.scrollHeight, ovClientH: ov2.clientHeight, ovScrollTop: ov2.scrollTop,
                    contentH: Math.round(last.bottom - first.top),
                    topGap: Math.round(first.top - r.top),
                    bottomGap: Math.round(r.bottom - last.bottom),
                    gridBottom: g ? Math.round(g.bottom) : null,
                    vh: window.innerHeight,
                    keypadBtn: (() => { const btns = grid ? [...grid.querySelectorAll('button')] : []; return btns.length; })(),
                };
            }''')
            print(f'=== {name} ({w}x{h}) ===')
            for k, v in m.items(): print(f'  {k}: {v}')
            await page.screenshot(path=f'/tmp/gf_pin_{name}.png')
            await ctx.close()
        await b.close()

asyncio.run(run())
print('SELESAI')
