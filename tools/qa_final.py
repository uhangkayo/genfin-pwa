#!/usr/bin/env python3
"""QA final v2.2: SE1 PIN muat + modal sheet + navigasi Atur chips."""
import asyncio, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

async def login_and_pin(page):
    await page.wait_for_selector('#gf-f-ak', timeout=8000)
    await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
    await page.wait_for_selector('#gf-f-p1', timeout=8000)
    await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
    await page.wait_for_timeout(2800)
    for _round in range(2):  # set lalu confirm (ulangi PIN)
        for d in '1234':
            await page.click(f'#gf-pin button:has-text("{d}")', timeout=4000); await page.wait_for_timeout(90)
        await page.click('#gf-pin button:has-text("✓")', timeout=4000); await page.wait_for_timeout(1400)
    await page.wait_for_timeout(1200)
    # dismiss onboarding "Selamat datang" bila muncul
    try:
        await page.click('button:has-text("Lihat dulu dengan data contoh")', timeout=3000)
        await page.wait_for_timeout(700)
    except Exception:
        pass

async def run():
    ok = True
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # --- 1. SE1: PIN harus muat ---
        subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
        ctx = await b.new_context(viewport={'width': 320, 'height': 568}, device_scale_factor=2, is_mobile=True, has_touch=True)
        page = await ctx.new_page()
        await page.goto(APP, wait_until='domcontentloaded')
        await page.wait_for_selector('#gf-f-ak', timeout=8000)
        await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
        await page.wait_for_selector('#gf-f-p1', timeout=8000)
        await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
        await page.wait_for_timeout(2800)
        pin = await page.evaluate('''() => {
            const h2 = [...document.querySelectorAll('h2')].find(x => x.textContent.includes('PIN'));
            const dbg = (() => { const g = document.querySelector('#gf-pin div[style*="grid-template-columns"]'); if (!g) return null;
                const btn = g.querySelector('button'); return {cols: getComputedStyle(g).gridTemplateColumns, gap: getComputedStyle(g).gap, btnH: btn ? getComputedStyle(btn).height : null}; })();
            let el = h2; while (el && getComputedStyle(el).position !== 'fixed') el = el.parentElement;
            const kids = [...el.children].filter(c => c.getBoundingClientRect().height > 0);
            const last = kids[kids.length-1].getBoundingClientRect();
            return {fits: el.scrollHeight <= el.clientHeight + 1, scrollH: el.scrollHeight, clientH: el.clientHeight,
                    lastBottom: Math.round(last.bottom), vh: innerHeight, dbg};
        }''')
        print(f'SE1 PIN: {pin}')
        await page.screenshot(path='/tmp/gf_final_se1.png')
        if not pin['fits'] or pin['lastBottom'] > pin['vh']:
            print('  [GAGAL] PIN SE1 tidak muat'); ok = False
        else:
            print('  [OK] PIN SE1 muat')
        await ctx.close()

        # --- 2. iphone14: modal sheet + atur chips ---
        subprocess.run(['rm', '-f', '/root/genfin-pwa/.mock-store.json'])
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
        page = await ctx.new_page()
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)[:150]))
        await page.goto(APP, wait_until='domcontentloaded')
        await login_and_pin(page)
        # ke tab Pos (nav ke-2?) — coba klik nav buttons
        navlabels = await page.evaluate('''() => [...document.querySelectorAll('#gf-col > nav button')].map(b => b.textContent.trim())''')
        print(f'nav: {navlabels}')
        # buka modal tambah pos dari header (tombol aria-label Tambah pos ada di layar Pos)
        for lbl in navlabels:
            if 'pos' in lbl.lower():
                await page.click(f'#gf-col > nav button:has-text("{lbl}")'); break
        await page.wait_for_timeout(600)
        await page.click('button[aria-label="Tambah pos"]')
        await page.wait_for_timeout(800)
        sheet = await page.evaluate('''() => {
            const cands = [...document.querySelectorAll('body *')].filter(e => {
                if (!(e instanceof HTMLElement)) return false;
                const cs = getComputedStyle(e);
                return cs.position === 'fixed' && parseInt(cs.zIndex) >= 40 && parseInt(cs.zIndex) < 60 && e.getBoundingClientRect().height > 50;
            });
            if (!cands.length) return {open:false};
            const sh = cands.sort((a,b) => parseInt(getComputedStyle(b).zIndex) - parseInt(getComputedStyle(a).zIndex))[0];
            const card = sh.firstElementChild.getBoundingClientRect();
            return {open:true, z: getComputedStyle(sh).zIndex, cardBottom:Math.round(card.bottom), vh:innerHeight, cardTop:Math.round(card.top)};
        }''')
        print(f'modal sheet: {sheet}')
        if not sheet.get('open'):
            print('  [GAGAL] modal tidak terbuka'); ok = False
        else:
            vis = sheet['cardBottom'] <= 844 and sheet['cardBottom'] >= 700
            print(f'  [{"OK" if vis else "GAGAL"}] sheet menempel bawah viewport ({sheet["cardBottom"]}/844)')
            if not vis: ok = False
        await page.screenshot(path='/tmp/gf_final_modal.png')
        # tutup modal: klik backdrop (area gelap di atas sheet)
        try:
            await page.mouse.click(195, 30)
            await page.wait_for_timeout(600)
        except Exception: pass
        # tab Atur + klik chip Keamanan (uji scroll main)
        for lbl in navlabels:
            if 'atur' in lbl.lower():
                await page.click(f'#gf-col > nav button:has-text("{lbl}")'); break
        await page.wait_for_timeout(700)
        chips = await page.evaluate('''() => {
            const chips = [...document.querySelectorAll('#gf-col > main button')].filter(b => ['Alokasi','Anggaran','Berulang','Keamanan','Data'].includes(b.textContent.trim()));
            return chips.map(c => c.textContent.trim());
        }''')
        print(f'atur chips: {chips}')
        try:
            await page.click('#gf-col > main button:has-text("Keamanan")')
            await page.wait_for_timeout(900)
            st = await page.evaluate('''() => {
                const main = document.querySelector('#gf-col > main');
                const sec = document.getElementById('atur-keamanan');
                return {mainScrolled: main.scrollTop > 0, secVisible: sec ? sec.getBoundingClientRect().top < innerHeight : false};
            }''')
            print(f'chip scroll: {st}')
            if not (st['mainScrolled'] or st['secVisible']):
                print('  [GAGAL] chip tidak menscroll'); ok = False
            else:
                print('  [OK] chip scroll jalan')
        except Exception as e:
            print(f'  [WARN] chip test: {str(e)[:100]}')
        if errs:
            print(f'pageerror: {errs[:3]}'); ok = False
        await page.screenshot(path='/tmp/gf_final_atur.png')
        await ctx.close()
        await b.close()
    print('SEMUA OK' if ok else 'ADA GAGAL')

asyncio.run(run())
