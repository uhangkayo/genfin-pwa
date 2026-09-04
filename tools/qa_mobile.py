#!/usr/bin/env python3
"""QA responsivitas mobile GenFin PWA — reproduksi viewport iPhone via Playwright."""
import asyncio, sys
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = ' MOCKKEY-MOCKKEY-MOCKKEY-1234 \n'   # bawa spasi+enter utk uji trim
PASS = 'qa-passphrase-123'

DEVICES = [
    ('iphone14', 390, 844, 3),
    ('iphoneSE', 375, 667, 2),
]

async def login(page, fresh):
    # gate access key
    await page.wait_for_selector('#gf-f-ak', timeout=8000)
    await page.fill('#gf-f-ak', KEY)
    await page.click('#gf-ok')
    if not fresh:
        # akun sudah ada di mock store: gate passphrase tunggal
        await page.wait_for_selector('#gf-f-pass', timeout=8000)
        await page.fill('#gf-f-pass', PASS)
        await page.click('#gf-ok')
        return
    # gate passphrase (buat baru)
    await page.wait_for_selector('#gf-f-p1', timeout=8000)
    await page.fill('#gf-f-p1', PASS)
    await page.fill('#gf-f-p2', PASS)
    ck = page.locator('#gf-f-remember-ck')
    if await ck.count():
        try: await ck.check()
        except Exception: pass
    await page.click('#gf-ok')

async def measure(page, label):
    m = await page.evaluate('''() => {
        const de = document.documentElement;
        const nav = document.querySelector('nav');
        const shell = document.querySelector('body > div, x-dc > div');
        const r = nav ? nav.getBoundingClientRect() : null;
        const col = document.querySelector('div[style*="max-width:468px"]') || shell;
        return {
            innerW: window.innerWidth, innerH: window.innerHeight,
            scrollH: de.scrollHeight, scrollW: de.scrollWidth,
            docH: document.body.scrollHeight,
            navBottom: r ? Math.round(r.bottom) : null,
            navH: r ? Math.round(r.height) : null,
            navTop: r ? Math.round(r.top) : null,
            hOverflow: de.scrollWidth > window.innerWidth + 1,
            gateVisible: !!document.querySelector('#gf-gate'),
        };
    }''')
    print(f'--- {label} ---')
    for k, v in m.items(): print(f'  {k}: {v}')
    return m

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for i, (name, w, h, dpr) in enumerate(DEVICES):
            import subprocess
            subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
            ctx = await b.new_context(viewport={'width': w, 'height': h},
                                      device_scale_factor=dpr, is_mobile=True,
                                      has_touch=True, locale='id-ID',
                                      timezone_id='Asia/Jakarta')
            page = await ctx.new_page()
            await page.goto(APP, wait_until='domcontentloaded')
            await page.wait_for_timeout(1200)
            await page.screenshot(path=f'/tmp/gf_{name}_gate.png')
            try:
                await login(page, fresh=True)
            except Exception as e:
                print(f'[{name}] login err: {e}')
                await page.screenshot(path=f'/tmp/gf_{name}_err.png')
            await page.wait_for_timeout(2500)
            # mungkin diminta buat PIN
            pin = page.locator('input[type="password"], input[type="tel"]').first
            try:
                if await pin.count() and await pin.is_visible():
                    await page.screenshot(path=f'/tmp/gf_{name}_pin.png')
            except Exception: pass
            await page.screenshot(path=f'/tmp/gf_{name}_home.png', full_page=False)
            await measure(page, name)
            # cek elemen yang keluar dari viewport horizontal
            over = await page.evaluate('''() => {
                const vw = window.innerWidth, out = [];
                document.querySelectorAll('body *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && (r.right > vw + 2 || r.left < -2)) {
                        const s = (el.getAttribute('style')||'').slice(0,90);
                        out.push(`${el.tagName}.${el.className&&el.className.toString().slice(0,20)} L${Math.round(r.left)} R${Math.round(r.right)} | ${s}`);
                    }
                });
                return out.slice(0, 12);
            }''')
            if over:
                print(f'  ELEMEN LUAR VIEWPORT ({len(over)}):')
                for o in over: print(f'    {o}')
            else:
                print('  Elemen luar viewport: TIDAK ADA')
            await ctx.close()
        await b.close()

asyncio.run(run())
print('SELESAI')
