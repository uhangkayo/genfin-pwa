#!/usr/bin/env python3
"""QA sync v2.3 — 3 skenario multi-perangkat (bug offline-loop, conflict, auto-refresh)."""
import asyncio, json, os, subprocess
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'
STORE = '/root/genfin-pwa/.mock-store.json'

def store():
    if not os.path.exists(STORE): return None
    return json.load(open(STORE))

def sv():
    s = store(); return (s or {}).get('v', 0) if (s or {}).get('enc') else 0

async def setup_a(page):
    await page.goto(APP, wait_until='domcontentloaded')
    await page.wait_for_selector('#gf-f-ak', timeout=8000)
    await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
    await page.wait_for_selector('#gf-f-p1', timeout=8000)
    await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
    await page.wait_for_timeout(2800)
    for _round in range(2):
        for d in '1234':
            await page.click(f'#gf-pin button:has-text("{d}")', timeout=4000); await page.wait_for_timeout(90)
        await page.click('#gf-pin button:has-text("✓")', timeout=4000); await page.wait_for_timeout(1400)
    await page.wait_for_timeout(1200)
    try:
        await page.click('button:has-text("Lihat dulu dengan data contoh")', timeout=3000)
        await page.wait_for_timeout(700)
    except Exception: pass

async def goto_atur(page):
    await page.click('#gf-col > nav button:has-text("Atur")', timeout=5000)
    await page.wait_for_timeout(600)

async def toggle_autolock(page, n=1):
    # expand section KEAMANAN lalu klik toggle "Kunci otomatis" (autoLock = data ter-persist)
    await page.evaluate("""() => {
        const already = [...document.querySelectorAll('div')].some(d => d.textContent.trim() === 'Kunci otomatis');
        if (already) return;
        const hdr = [...document.querySelectorAll('div')].find(d => d.textContent.trim() === 'PIN, Kunci & Pemulihan');
        if (hdr) { let row = hdr; for (let i=0;i<4 && row.parentElement;i++){ row = row.parentElement; if (row.querySelector('svg')) break; } row.click(); }
    }""")
    await page.wait_for_timeout(700)
    for _ in range(n):
        await page.evaluate("""() => {
            const div = [...document.querySelectorAll('div')].find(d => d.textContent.trim() === 'Kunci otomatis');
            if (!div) throw new Error('toggle Kunci otomatis tidak ditemukan (section tidak ter-expand?)');
            let row = div; for (let i=0;i<3 && row.parentElement;i++){ row = row.parentElement; if (row.querySelector('button')) break; }
            row.querySelector('button').click();
        }""")
        await page.wait_for_timeout(400)

async def pin_unlock(page):
    await page.wait_for_selector('#gf-pin button', timeout=15000)
    for d in '1234':
        await page.click(f'#gf-pin button:has-text("{d}")', timeout=6000); await page.wait_for_timeout(120)
    try:  # tahap unlock auto-submit setelah 4 digit — ✓ hanya ada di tahap set/confirm
        await page.click('#gf-pin button:has-text("✓")', timeout=1500)
    except Exception:
        pass
    await page.wait_for_timeout(1500)

async def run():
    ok = True
    def check(cond, msg):
        nonlocal ok
        print(f'  [{"OK" if cond else "GAGAL"}] {msg}')
        if not cond: ok = False

    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctxA = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        pgA = await ctxA.new_page()
        errs = []
        pgA.on('pageerror', lambda e: errs.append(str(e)[:120]))

        print('=== SETUP perangkat A (migrasi + PIN + onboard) ===')
        await setup_a(pgA)
        await page_wait_store(1)
        v1 = sv(); print(f'  server v={v1}'); check(v1 >= 1, 'data awal tersinkron (v>=1)')

        # ---------- SKENARIO A: offline multi-edit (dulu = reload loop abadi) ----------
        print('=== SKENARIO A: 2 edit offline → online (single-slot queue) ===')
        await pgA.evaluate("() => { window.__qaA = 'hidup'; }")
        await ctxA.set_offline(True)
        await goto_atur(pgA)
        await toggle_autolock(pgA); await pgA.wait_for_timeout(2600)
        q1 = await pgA.evaluate("() => (JSON.parse(localStorage.getItem('gf_pending')||'[]')).length")
        check(q1 == 1, f'edit-1 offline masuk antrian (len={q1})')
        await toggle_autolock(pgA); await pgA.wait_for_timeout(2600)
        q2 = await pgA.evaluate("() => (JSON.parse(localStorage.getItem('gf_pending')||'[]')).length")
        check(q2 == 1, f'edit-2 MENGGANTI item lama — single-slot, bukan push (len={q2})')
        await ctxA.set_offline(False)
        await pgA.evaluate("() => dispatchEvent(new Event('online'))")
        await pgA.wait_for_timeout(3000)
        v2 = sv()
        qp = await pgA.evaluate("() => (JSON.parse(localStorage.getItem('gf_pending')||'[]')).length")
        marker = await pgA.evaluate("() => window.__qaA")
        gate = await pgA.evaluate("() => !!document.getElementById('gf-gate')")
        check(v2 == v1 + 1, f'server maju tepat 1 versi ({v1}→{v2}) — snapshot terakhir yang menang')
        check(qp == 0, 'antrian kosong setelah flush')
        check(marker == 'hidup', 'TIDAK ada reload loop (marker halaman bertahan)')
        check(not gate, 'tidak ada kartu conflict')

        # ---------- SKENARIO B: conflict — perangkat B menang ----------
        print('=== SKENARIO B: A offline-edit vs B online-save → conflict rapi ===')
        await ctxA.set_offline(True)
        await toggle_autolock(pgA); await pgA.wait_for_timeout(2600)
        qb = await pgA.evaluate("() => (JSON.parse(localStorage.getItem('gf_pending')||'[]')).length")
        check(qb == 1, 'A punya 1 item antrian saat offline')

        ctxB = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        pgB = await ctxB.new_page()
        await pgB.goto(APP, wait_until='domcontentloaded')
        await pgB.wait_for_selector('#gf-f-ak', timeout=8000)
        await pgB.fill('#gf-f-ak', KEY); await pgB.click('#gf-ok')
        await pgB.wait_for_selector('#gf-f-pass', timeout=8000)
        await pgB.fill('#gf-f-pass', PASS); await pgB.click('#gf-ok')   # remember default ON
        await pgB.wait_for_timeout(2500)
        await pin_unlock(pgB)
        await goto_atur(pgB)
        await toggle_autolock(pgB)
        await pgB.wait_for_timeout(3000)
        v3 = sv(); check(v3 >= v2 + 1, f'B tersimpan online ({v2}→{v3})')  # expand-section juga 1 mutasi

        await ctxA.set_offline(False)
        await pgA.evaluate("() => dispatchEvent(new Event('online'))")
        await pgA.wait_for_timeout(2500)
        gateTxt = await pgA.evaluate("() => { var g = document.getElementById('gf-gate'); return g ? g.textContent : ''; }")
        check('perangkat lain' in gateTxt, 'A dapat kartu conflict (bukan alert mentah)')
        qAfter = await pgA.evaluate("() => (JSON.parse(localStorage.getItem('gf_pending')||'[]')).length")
        check(qAfter == 0, 'antrian A dibuang saat conflict (anti loop)')
        try:
            await pgA.click('#gf-ok', timeout=3000)   # tombol Muat Ulang
        except Exception: pass
        await pgA.wait_for_timeout(4000)
        cacheV = await pgA.evaluate("() => { var c = JSON.parse(localStorage.getItem('gf_cache')||'null'); return c ? c.v : -1; }")
        check(cacheV == v3, f'A setelah reload hidrasi versi terbaru B (cache v={cacheV}, server={v3})')

        # ---------- SKENARIO C: server lebih baru → auto-refresh tanpa sentuh ----------
        print('=== SKENARIO C: B edit lagi → A auto-reload (sinkron 2 arah) ===')
        await toggle_autolock(pgB)
        await pgB.wait_for_timeout(3000)
        v4 = sv(); check(v4 == v3 + 1, f'B naikkan versi ({v3}→{v4})')
        await pgA.evaluate("() => { try{sessionStorage.removeItem('gf_rl');}catch(e){} }")  # izinkan auto-reload dlm QA
        await pgA.wait_for_timeout(21000)   # lewati throttle 20 dtk checkRemote (by design anti-hammer)
        await pgA.evaluate("() => dispatchEvent(new Event('focus'))")
        try:
            await pgA.wait_for_url(APP, timeout=8000)   # tunggu reload
        except Exception: pass
        await pgA.wait_for_timeout(3500)
        cacheV2 = await pgA.evaluate("() => { var c = JSON.parse(localStorage.getItem('gf_cache')||'null'); return c ? c.v : -1; }")
        check(cacheV2 == v4, f'A ikut memuat versi terbaru otomatis (cache v={cacheV2}, server={v4})')

        if errs:
            print(f'  pageerror: {errs[:3]}'); ok = False
        await ctxA.close(); await ctxB.close(); await b.close()
    print('SEMUA OK — sinkronisasi bersih' if ok else 'ADA GAGAL')

async def page_wait_store(minv, tries=40):
    for _ in range(tries):
        if sv() >= minv: return True
        await asyncio.sleep(0.5)
    return False

asyncio.run(run())
