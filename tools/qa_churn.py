#!/usr/bin/env python3
"""Reproduce version churn: dua perangkat idle → pantau tiap save, dekripsi, diff field."""
import asyncio, base64, hashlib, json, os, subprocess
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'
STORE = '/root/genfin-pwa/.mock-store.json'

def dec(store):
    key = hashlib.pbkdf2_hmac('sha256', PASS.encode(), base64.b64decode(store['salt']), 210000, 32)
    pt = AESGCM(key).decrypt(base64.b64decode(store['iv']), base64.b64decode(store['ct']), None)
    return json.loads(pt.decode())

def flat(d, p=''):
    out = {}
    for k, v in (d or {}).items():
        kk = f'{p}.{k}' if p else k
        if isinstance(v, dict): out.update(flat(v, kk))
        elif isinstance(v, list): out[kk] = json.dumps(v, sort_keys=True)[:120]
        else: out[kk] = v
    return out

async def setup(page):
    await page.goto(APP, wait_until='domcontentloaded')
    await page.wait_for_selector('#gf-f-ak', timeout=8000)
    await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
    await page.wait_for_selector('#gf-f-p1', timeout=8000)
    await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
    await page.wait_for_timeout(2800)
    for _r in range(2):
        for d in '1234':
            await page.click(f'#gf-pin button:has-text("{d}")'); await page.wait_for_timeout(90)
        await page.click('#gf-pin button:has-text("✓")'); await page.wait_for_timeout(1400)
    await page.wait_for_timeout(1000)
    try:
        await page.click('button:has-text("Lihat dulu dengan data contoh")', timeout=3000); await page.wait_for_timeout(700)
    except Exception: pass

async def run():
    subprocess.run(['rm', '-f', STORE])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctxA = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        pgA = await ctxA.new_page()
        await setup(pgA)
        await asyncio.sleep(3)
        ctxB = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        pgB = await ctxB.new_page()
        await pgB.goto(APP, wait_until='domcontentloaded')
        await pgB.wait_for_selector('#gf-f-ak', timeout=8000)
        await pgB.fill('#gf-f-ak', KEY); await pgB.click('#gf-ok')
        await pgB.wait_for_selector('#gf-f-pass', timeout=8000)
        await pgB.fill('#gf-f-pass', PASS); await pgB.click('#gf-ok')
        await pgB.wait_for_timeout(2500)
        # B unlock PIN
        for d in '1234':
            await pgB.click(f'#gf-pin button:has-text("{d}")'); await pgB.wait_for_timeout(120)
        await pgB.wait_for_timeout(1500)
        print('=== dua perangkat idle — pantau churn 90 dtk ===')
        prev_v, prev_flat = None, None
        for i in range(90):
            await asyncio.sleep(1)
            if not os.path.exists(STORE): continue
            s = json.load(open(STORE))
            if not s.get('enc'): continue
            if s['v'] != prev_v:
                try: obj = dec(s)
                except Exception as e: print(f'v={s["v"]} decrypt fail {e}'); prev_v = s['v']; continue
                fl = flat(obj)
                if prev_flat is not None:
                    ch = {k: (prev_flat.get(k), fl.get(k)) for k in set(prev_flat) | set(fl) if prev_flat.get(k) != fl.get(k)}
                    print(f'v {prev_v}→{s["v"]} DIFF: {json.dumps(ch, default=str)[:400]}')
                else:
                    print(f'v={s["v"]} baseline ({len(fl)} field)')
                prev_v, prev_flat = s['v'], fl
        await b.close()

asyncio.run(run())
