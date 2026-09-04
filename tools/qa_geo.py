#!/usr/bin/env python3
"""QA geometri iOS — cari penyebab gap bawah di iPhone."""
import asyncio, json
from playwright.async_api import async_playwright

APP = 'http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec'
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'
PASS = 'qa-passphrase-123'

MEASURE = """() => {
  const r = (el) => { const b = el.getBoundingClientRect(); return {t:+b.top.toFixed(1), b:+b.bottom.toFixed(1), l:+b.left.toFixed(1), rt:+b.right.toFixed(1), w:+b.width.toFixed(1), h:+b.height.toFixed(1)}; };
  const shell = document.querySelector('#gf-shell');
  const col = document.querySelector('#gf-col');
  const main = document.querySelector('#gf-col > main');
  const nav = document.querySelector('#gf-col > nav');
  const vv = window.visualViewport;
  // elemen yang meluber horizontal / vertikal keluar layout viewport
  const wide = [];
  document.querySelectorAll('body *').forEach(el => {
    const b = el.getBoundingClientRect();
    if (b.width > 0 && (b.right > window.innerWidth + 1.5 || b.left < -1.5)) {
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed' && b.right <= window.innerWidth + 1.5) return;
      wide.push({tag: el.tagName, id: el.id || '', cls: (el.className||'').toString().slice(0,30),
                 txt: (el.textContent||'').trim().slice(0,25), rect: r(el),
                 pos: cs.position, minw: cs.minWidth, wpx: cs.width});
    }
  });
  const html = document.documentElement, body = document.body;
  return {
    inner: {w: window.innerWidth, h: window.innerHeight},
    client: {w: html.clientWidth, h: html.clientHeight},
    scroll: {w: html.scrollWidth, h: html.scrollHeight, bw: body.scrollWidth, bh: body.scrollHeight},
    vv: vv ? {w: +vv.width.toFixed(1), h: +vv.height.toFixed(1), scale: vv.scale, offsetTop: vv.offsetTop, pageTop: +vv.pageTop.toFixed(1)} : null,
    shellPos: getComputedStyle(shell).position,
    rects: {shell: r(shell), col: r(col), main: r(main), nav: r(nav)},
    navGapBottom: +(window.innerHeight - nav.getBoundingClientRect().bottom).toFixed(1),
    colGapBottom: +(window.innerHeight - col.getBoundingClientRect().bottom).toFixed(1),
    wideCount: wide.length, wideSample: wide.slice(0, 12),
    dpr: window.devicePixelRatio
  };
}"""

async def unlock(page):
    await page.goto(APP, wait_until='domcontentloaded')
    await page.wait_for_timeout(1500)
    try:  # keluarga baru: key + passphrase (2 tahap)
        await page.wait_for_selector('#gf-f-ak', timeout=5000)
        await page.fill('#gf-f-ak', KEY); await page.click('#gf-ok')
        await page.wait_for_selector('#gf-f-p1', timeout=8000)
        await page.fill('#gf-f-p1', PASS); await page.fill('#gf-f-p2', PASS); await page.click('#gf-ok')
        await page.wait_for_timeout(3000)
    except Exception:  # keluarga sudah ada: gate passphrase saja
        try:
            await page.wait_for_selector('#gf-f-pass', timeout=4000)
            await page.fill('#gf-f-pass', PASS); await page.click('#gf-ok')
            await page.wait_for_timeout(3000)
        except Exception:
            pass
    await page.wait_for_selector('#gf-pin button', timeout=15000)
    for d in '1234':
        await page.click(f'#gf-pin button:has-text("{d}")'); await page.wait_for_timeout(100)
    try: await page.click('#gf-pin button:has-text("✓")', timeout=1500)
    except Exception: pass
    await page.wait_for_timeout(1800)
    try:
        await page.click('button:has-text("Lihat dulu dengan data contoh")', timeout=2500)
        await page.wait_for_timeout(800)
    except Exception: pass

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        results = {}
        for name, vp in [
            ('iphone14', {'width':390,'height':844}),
            ('se3',      {'width':375,'height':667}),
            ('pmax',     {'width':430,'height':932}),
        ]:
            ctx = await b.new_context(viewport=vp, is_mobile=True, has_touch=True,
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1')
            pg = await ctx.new_page()
            await unlock(pg)
            m = await pg.evaluate(MEASURE)
            results[name] = m
            print(f'\n===== {name} ({vp["width"]}x{vp["height"]}) =====')
            print(json.dumps(m, indent=1)[:2400])
            await pg.screenshot(path=f'/tmp/qa_geo_{name}.png')
            await ctx.close()
        await b.close()

asyncio.run(run())
