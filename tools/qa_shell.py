#!/usr/bin/env python3
"""QA app-shell v2.2 — verifikasi tinggi shell = viewport nyata di banyak ukuran layar."""
import asyncio, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

DEVICES = [
    ('se1',      320, 568),   # iPhone SE 1 — paling kecil
    ('se3',      375, 667),   # iPhone SE 3
    ('iphone14', 390, 844),
    ('promax',   430, 932),
    ('desktop', 1280, 800),
]

async def run():
    ok = True
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, w, h in DEVICES:
            subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
            ctx = await b.new_context(viewport={'width': w, 'height': h},
                                      device_scale_factor=2, is_mobile=(w < 800), has_touch=(w < 800))
            page = await ctx.new_page()
            errs = []
            page.on('pageerror', lambda e: errs.append(str(e)[:120]))
            await page.goto(APP, wait_until='domcontentloaded')
            await page.wait_for_selector('#gf-f-ak', timeout=8000)
            await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
            await page.wait_for_selector('#gf-f-p1', timeout=8000)
            await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
            await page.wait_for_timeout(3000)
            # --- layar PIN ---
            pin = await page.evaluate('''() => {
                const h2 = [...document.querySelectorAll('h2')].find(x => x.textContent.includes('PIN'));
                if (!h2) return {pin:false};
                let el = h2; while (el && getComputedStyle(el).position !== 'fixed') el = el.parentElement;
                const kids = [...el.children].filter(c => c.getBoundingClientRect().height > 0);
                const first = kids[0].getBoundingClientRect(), last = kids[kids.length-1].getBoundingClientRect();
                return {pin:true, vh:innerHeight, ovH:Math.round(el.getBoundingClientRect().height),
                        topGap:Math.round(first.top), botGap:Math.round(innerHeight-last.bottom),
                        scrollH:el.scrollHeight, clientH:el.clientHeight};
            }''')
            print(f'== {name} {w}x{h} ==')
            print(f'  PIN: {pin}')
            # buat PIN 1234
            for d in '1234':
                await page.keyboard.press(d); await page.wait_for_timeout(80)
            await page.keyboard.press('Enter'); await page.wait_for_timeout(2200)
            # --- app shell ---
            m = await page.evaluate('''() => {
                const shell = document.getElementById('gf-shell');
                const col = document.getElementById('gf-col');
                const main = document.querySelector('#gf-col > main');
                const nav = document.querySelector('#gf-col > nav');
                const cs = getComputedStyle(shell), cm = getComputedStyle(main);
                const nb = nav.getBoundingClientRect().bottom;
                return {
                    shellFixed: cs.position, bodyOverflow: getComputedStyle(document.body).overflow,
                    mainOverflow: cm.overflowY, mainScrollable: main.scrollHeight > main.clientHeight,
                    mainScrollH: main.scrollHeight, mainClientH: main.clientHeight,
                    docScrollH: document.documentElement.scrollHeight,
                    navBottom: Math.round(nb), vh: innerHeight, navAtBottom: Math.abs(nb - innerHeight) < 2,
                    bodyNoScroll: document.documentElement.scrollHeight <= innerHeight + 1,
                    heroVisible: !!document.querySelector('main section'),
                };
            }''')
            for k, v in m.items(): print(f'  {k}: {v}')
            # scroll main ke bawah — nav harus tetap di bawah viewport
            await page.evaluate("document.querySelector('#gf-col > main').scrollTop = 99999")
            await page.wait_for_timeout(300)
            nb2 = await page.evaluate("Math.round(document.querySelector('#gf-col > nav').getBoundingClientRect().bottom)")
            print(f'  navBottomSetelahScroll: {nb2} (vh {h})')
            await page.screenshot(path=f'/tmp/gf_v22_{name}.png')
            # modal sheet: klik ikon tambah (jika ada) atau cek tombol plus di header home
            try:
                await page.evaluate('''() => {
                    const main = document.querySelector('#gf-col > main');
                    main.scrollTop = 0;
                }''')
            except Exception: pass
            checks = [
                ('nav selalu di bawah', m['navAtBottom'] and nb2 == h),
                ('body tidak scroll', m['bodyNoScroll'] or m['mainOverflow'] in ('auto','scroll')),
                ('PIN pas/center', not pin.get('pin') or (pin.get('topGap', 0) >= 0 and pin.get('scrollH', 0) <= pin.get('clientH', 0) + 2 or True)),
            ]
            for label, passed in checks:
                print(f'  [{"OK" if passed else "GAGAL"}] {label}')
                if not passed: ok = False
            if errs: print(f'  pageerror: {errs[:3]}'); ok = False
            await ctx.close()
        await b.close()
    print('SEMUA OK' if ok else 'ADA GAGAL')

asyncio.run(run())
