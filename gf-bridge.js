/* ============================================================
 * GenFin Bridge v2.1 — E2EE (AES-GCM 256 + PBKDF2) + Apps Script API
 *
 * PERBAIKAN v2.1:
 *  - ?api= TIDAK lagi dihapus dari URL → iOS menangkap URL lengkap
 *    saat "Add to Home Screen" (storage PWA standalone iOS terpisah
 *    dari Safari — tanpa ini, icon home screen membuka app kosong).
 *  - Semua input di-TRIM (paste dari Gmail/execution log iOS sering
 *    membawa spasi/enter tak terlihat → key selalu "salah").
 *  - Checkbox "tetap terbuka 7 hari" default AKTIF.
 *  - Pemulihan Access Key via email pemilik (action sendkey) —
 *    tanpa perlu buka execution log Apps Script.
 *  - Deteksi "server belum setup" via doGet (setup flag).
 *  - Boot offline: salinan ciphertext terakhir di-cache lokal;
 *    app tetap bisa dibuka tanpa koneksi, tulahan masuk antrian.
 *  - Halaman error pakai kartu + tombol coba lagi (bukan alert).
 * ============================================================ */
(function () {
  'use strict';

  /* ---------- config: pasang API lewat ?api=<URL exec> sekali ---------- */
  try {
    var u = new URLSearchParams(location.search).get('api');
    if (u) { localStorage.setItem('gf_api_url', u); } // JANGAN strip — dipakai saat Add to Home Screen
  } catch (e) {}
  var API = null;
  try { API = localStorage.getItem('gf_api_url'); } catch (e) {}

  /* ---------- util ---------- */
  var TE = new TextEncoder(), TD = new TextDecoder();
  function b64(buf) { var b = new Uint8Array(buf), s = ''; for (var i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); return btoa(s); }
  function unb64(s) { var bin = atob(s), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  function rndB64(n) { return b64(crypto.getRandomValues(new Uint8Array(n))); }
  function api(body) {
    return fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' }, // simple request → tanpa CORS preflight
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }
  function apiGet() { return fetch(API).then(function (r) { return r.json(); }); }

  /* ---------- state ---------- */
  var key = null, saltB64 = null, ver = 0, AK = null;
  try { AK = (localStorage.getItem('gf_ak') || '').trim() || null; } catch (e) {}
  var resolveReady, ready = new Promise(function (r) { resolveReady = r; });

  /* ---------- crypto ---------- */
  function derive(pass, salt, extractable) {
    return crypto.subtle.importKey('raw', TE.encode(pass), 'PBKDF2', false, ['deriveKey'])
      .then(function (k) {
        return crypto.subtle.deriveKey(
          { name: 'PBKDF2', salt: unb64(salt), iterations: 210000, hash: 'SHA-256' },
          k, { name: 'AES-GCM', length: 256 }, extractable, ['encrypt', 'decrypt']
        );
      });
  }
  function encryptStr(s) {
    var iv = crypto.getRandomValues(new Uint8Array(12));
    return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, TE.encode(s))
      .then(function (ct) { return { iv: b64(iv), ct: b64(ct) }; });
  }
  function decryptStr(ivB64, ctB64) {
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(ivB64) }, key, unb64(ctB64))
      .then(function (pt) { return TD.decode(pt); });
  }

  /* ---------- kunci yang diingat perangkat (7 hari) ---------- */
  function saveRemember() {
    if (!key || !key.extractable) return;
    crypto.subtle.exportKey('raw', key).then(function (raw) {
      try { localStorage.setItem('gf_remember', JSON.stringify({ k: b64(raw), salt: saltB64, exp: Date.now() + 7 * 24 * 3600 * 1000 })); } catch (e) {}
    });
  }
  function loadRemember() {
    try {
      var r = JSON.parse(localStorage.getItem('gf_remember') || 'null');
      if (!r || !r.k || r.exp < Date.now()) return null;
      return crypto.subtle.importKey('raw', unb64(r.k), { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
        .then(function (k) { saltB64 = r.salt; return k; });
    } catch (e) { return null; }
  }

  /* ---------- cache offline (ciphertext terakhir yang berhasil diambil) ---------- */
  function writeCache(c) { try { localStorage.setItem('gf_cache', JSON.stringify(c)); } catch (e) {} }
  function readCache() { try { return JSON.parse(localStorage.getItem('gf_cache') || 'null'); } catch (e) { return null; } }

  /* ---------- antrian offline ---------- */
  function queue() { try { return JSON.parse(localStorage.getItem('gf_pending') || '[]'); } catch (e) { return []; } }
  function setQueue(q) { try { localStorage.setItem('gf_pending', JSON.stringify(q)); } catch (e) {} }
  function flushQueue() {
    var q = queue();
    if (!q.length || !key) return Promise.resolve();
    var item = q[0];
    return api({ action: 'save', key: AK, base: item.base, iv: item.iv, ct: item.ct, salt: saltB64 })
      .then(function (r) {
        if (r.conflict) { alert('Data di perangkat lain lebih baru.\nMemuat ulang agar tidak ada yang hilang…'); location.reload(); return; }
        if (r.err) return; // coba lagi nanti
        ver = r.v; q.shift(); setQueue(q); flushQueue();
      }).catch(function () { /* offline, coba lagi */ });
  }
  ['online', 'focus', 'visibilitychange'].forEach(function (ev) {
    addEventListener(ev, function () { flushQueue(); });
  });
  setInterval(flushQueue, 60000);

  /* ---------- gerbang UI ---------- */
  var CSS =
    '#gf-gate{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;' +
    'background:linear-gradient(160deg,#0b3d2e 0%,#0e5941 60%,#12805a 100%);font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;' +
    '-webkit-backdrop-filter:blur(6px);}' +
    '#gf-gate .gf-card{background:rgba(255,255,255,.98);border-radius:20px;padding:26px 22px;width:min(88vw,340px);box-shadow:0 18px 50px rgba(0,0,0,.4);}' +
    '#gf-gate .gf-logo{width:54px;height:54px;border-radius:14px;background:linear-gradient(150deg,#0b3d2e,#16a34a);color:#fbbf24;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;margin:0 auto 10px;}' +
    '#gf-gate h1{font-size:17px;margin:2px 0 2px;text-align:center;color:#0b3d2e;}' +
    '#gf-gate p{font-size:12.5px;color:#6b7280;text-align:center;margin:0 0 14px;line-height:1.45;white-space:pre-line;}' +
    '#gf-gate input{width:100%;box-sizing:border-box;border:1.6px solid #d1d5db;border-radius:11px;padding:11px 12px;font-size:15px;margin-bottom:10px;}' +
    '#gf-gate input:focus{border-color:#16a34a;outline:none;}' +
    '#gf-gate button{width:100%;border:0;border-radius:11px;padding:12px;font-size:15px;font-weight:700;color:#fff;background:linear-gradient(150deg,#0b3d2e,#16a34a);cursor:pointer;}' +
    '#gf-gate button:active{opacity:.85;}' +
    '#gf-gate .gf-err{color:#dc2626;font-size:12.5px;text-align:center;margin:-4px 0 8px;min-height:15px;line-height:1.4;}' +
    '#gf-gate label{display:flex;gap:8px;align-items:center;font-size:12px;color:#6b7280;margin:-4px 0 10px;}' +
    '#gf-gate a{display:block;text-align:center;margin:-2px 0 12px;font-size:12px;color:#0b3d2e;text-decoration:underline;}' +
    '#gf-gate .gf-badge{position:fixed;bottom:10px;left:50%;transform:translateX(-50%);color:rgba(255,255,255,.75);font-size:10.5px;white-space:nowrap;}';
  function gate(opts) {
    // opts: {title, sub, fields:[{id,type,placeholder,label?,checked?}], button, check?, link?:{text,onClick}}
    return new Promise(function (resolve) {
      var st = document.createElement('style'); st.textContent = CSS; document.documentElement.appendChild(st);
      var d = document.createElement('div'); d.id = 'gf-gate';
      var inputs = (opts.fields || []).map(function (f) {
        return (f.label ? '<label><input type="checkbox" id="gf-f-' + f.id + '-ck" style="width:auto;margin:0"' + (f.checked ? ' checked' : '') + '> ' + f.label + '</label>' : '') +
          '<input id="gf-f-' + f.id + '" type="' + (f.type || 'text') + '" placeholder="' + f.placeholder + '" autocomplete="off">';
      }).join('');
      var link = opts.link ? '<a href="#" id="gf-link">' + opts.link.text + '</a>' : '';
      d.innerHTML = '<div class="gf-card"><div class="gf-logo">G</div><h1>' + opts.title + '</h1><p>' + opts.sub + '</p>' +
        '<div class="gf-err" id="gf-err"></div>' + inputs + link +
        '<button id="gf-ok">' + opts.button + '</button></div>' +
        '<div class="gf-badge">GenFin • terenkripsi ujung-ke-ujung</div>';
      document.documentElement.appendChild(d);
      var f0 = (opts.fields || [])[0];
      var first = f0 && document.getElementById('gf-f-' + f0.id); if (first) first.focus();
      if (opts.link) {
        document.getElementById('gf-link').addEventListener('click', function (e) {
          e.preventDefault();
          opts.link.onClick(function (msg, ok) {
            var el = document.getElementById('gf-err');
            if (el) { el.textContent = msg; el.style.color = ok ? '#16a34a' : '#dc2626'; }
          });
        });
      }
      function submit() {
        var vals = {};
        (opts.fields || []).forEach(function (f) {
          vals[f.id] = ((document.getElementById('gf-f-' + f.id) || {}).value || '');
          var ck = document.getElementById('gf-f-' + f.id + '-ck');
          vals[f.id + '_ck'] = ck ? ck.checked : false;
        });
        var bad = opts.check ? opts.check(vals) : null;
        if (bad) { var el = document.getElementById('gf-err'); el.textContent = bad; el.style.color = '#dc2626'; return; }
        d.remove(); resolve(vals);
      }
      document.getElementById('gf-ok').addEventListener('click', submit);
      d.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    });
  }

  function fail(msg) {
    gate({ title: 'GenFin', sub: msg, fields: [], button: 'Coba Lagi' }).then(function () { location.reload(); });
  }

  /* ---------- bootstrap ---------- */
  function boot() {
    var rem = loadRemember();
    var pre = rem ? rem.then(function (k) { key = k; }) : Promise.resolve();
    pre.then(function () { return api({ action: 'meta', key: AK }); })
      .then(function (m) {
        if (m.err === 'rate') return fail('Terlalu banyak percobaan gagal.\nTunggu sekitar 15 menit, lalu buka lagi.');
        if (m.err === 'auth') return authFail();
        if (!m.hasEnc) {
          if (m.hasLegacy) return migrate();   // data lama plaintext → enkripsi sekarang
          return freshInstall();               // Sheet kosong → set passphrase baru
        }
        saltB64 = m.salt;
        if (key) return fetchState();          // kunci hasil "ingat perangkat" — langsung
        return askPass().then(fetchState);
      })
      .catch(function () { offlineOpen(); });
  }

  /* key ditolak: bedakan "server belum setup" vs "key salah" */
  function authFail() {
    return apiGet().then(function (info) {
      if (info && info.setup === false) return notSetup();
      return askKey(!!AK);
    }).catch(function () { return askKey(false); });
  }

  function askKey(wasStored) {
    return gate({
      title: 'GenFin',
      sub: wasStored
        ? 'Access Key perangkat ini ditolak server — kemungkinan key sudah di-reset.\nMasukkan Access Key terbaru (cek email pemilik).'
        : 'Masukkan Access Key keluarga.\nCukup sekali untuk perangkat ini — setelah itu tidak diminta lagi.',
      fields: [{ id: 'ak', placeholder: 'Access Key', type: 'password' }],
      button: 'Buka',
      link: { text: 'Belum punya / lupa Access Key? Kirim ke email pemilik', onClick: sendKeyLink },
      check: function (v) { return v.ak.trim().length < 16 ? 'Access Key terlalu pendek — salin utuh dari email.' : null; }
    }).then(function (v) {
      AK = v.ak.trim(); try { localStorage.setItem('gf_ak', AK); } catch (e) {}
      return boot();
    });
  }

  function sendKeyLink(cb) {
    api({ action: 'sendkey' }).then(function (r) {
      if (r && r.ok) cb('Access Key dikirim ke Gmail pemilik akun Google.\nCek kotak masuk (dan Spam), salin key-nya, lalu tempel di sini.', true);
      else if (r && r.err === 'rate') cb('Baru saja dikirim — cek email pemilik dulu. Bisa minta lagi 10 menit lagi.', false);
      else if (r && r.err === 'nosetup') cb('Server belum di-setup. Jalankan setupGenFin di Apps Script (Extensions ▸ Apps Script ▸ Run), lalu kembali.', false);
      else if (r && r.err === 'unknown') cb('Server masih pakai Code.gs lama. Ganti dengan Code.gs terbaru, lalu Deploy ▸ Manage deployments ▸ Edit ▸ New version.', false);
      else cb('Pengiriman gagal. Coba beberapa saat lagi.', false);
    }).catch(function () { cb('Tidak bisa menghubungi server. Periksa koneksi internet.', false); });
  }

  function notSetup() {
    return gate({
      title: 'Server belum siap',
      sub: 'setupGenFin belum dijalankan di server.\n\nBuka Spreadsheet GenFin ▸ Extensions ▸ Apps Script ▸ pilih fungsi setupGenFin ▸ Run.\nAccess Key dikirim otomatis ke Gmail Anda, lalu buka lagi aplikasi ini.',
      fields: [], button: 'Sudah — Buka Lagi'
    }).then(function () { location.reload(); });
  }

  function needInstall() {
    return gate({
      title: 'GenFin belum terpasang',
      sub: 'Aplikasi ini belum terhubung ke server.\n\nCara pasang: buka link instal (yang mengandung ?api=...) dari chat, lalu dari halaman itu: Share ▸ Add to Home Screen.',
      fields: [], button: 'Muat Ulang'
    }).then(function () { location.reload(); });
  }

  function askPass(msg) {
    return gate({
      title: 'GenFin terkunci',
      sub: msg || 'Masukkan passphrase untuk mendekripsi data.',
      fields: [{ id: 'pass', placeholder: 'Passphrase', type: 'password', label: 'Tetap terbuka di perangkat ini (7 hari)', checked: true }],
      button: 'Buka Kunci',
      check: function (v) { return v.pass.trim().length < 4 ? 'Isi passphrase.' : null; }
    }).then(function (v) {
      return derive(v.pass.trim(), saltB64, v.pass_ck).then(function (k) { key = k; if (v.pass_ck) saveRemember(); });
    });
  }

  function unlockLoop() {
    return askPass('Passphrase salah — coba lagi.').then(fetchState);
  }

  function newPass(sub) {
    return gate({
      title: 'Buat Passphrase Data',
      sub: sub,
      fields: [
        { id: 'p1', placeholder: 'Passphrase (min. 10 karakter)', type: 'password' },
        { id: 'p2', placeholder: 'Ulangi passphrase', type: 'password', label: 'Tetap terbuka di perangkat ini (7 hari)', checked: true }
      ],
      button: 'Enkripsi & Simpan',
      check: function (v) {
        var a = v.p1.trim(), b = v.p2.trim();
        if (a.length < 10) return 'Minimal 10 karakter — ini yang melindungi data Anda.';
        if (a !== b) return 'Kedua isian belum sama.';
        return null;
      }
    }).then(function (v) {
      saltB64 = rndB64(16);
      return derive(v.p1.trim(), saltB64, v.p2_ck).then(function (k) { key = k; if (v.p2_ck) saveRemember(); });
    });
  }

  function migrate() {
    return newPass('Data lama akan dienkripsi sekarang.\nPassphrase INI kunci baru Anda — JANGAN lupa, tidak ada reset.')
      .then(function () {
        return api({ action: 'get', key: AK }).then(function (r) {
          if (!r.legacy) return '';
          return encryptStr(r.legacy).then(function (e) {
            return api({ action: 'save', key: AK, base: 0, iv: e.iv, ct: e.ct, salt: saltB64 })
              .then(function (res) { ver = res.v || 1; }); // sinkronkan versi agar save berikutnya tidak false-conflict
          }).then(function () { return r.legacy; });
        });
      }).then(function (json) { hydrate(json); });
  }

  function freshInstall() {
    return newPass('Sheet masih kosong. Buat passphrase untuk mengenkripsi seluruh data GenFin.')
      .then(function () { hydrate(''); });
  }

  function fetchState() {
    return api({ action: 'get', key: AK }).then(function (r) {
      if (!r.enc) return hydrate(r.legacy || '');
      ver = r.v;
      writeCache({ v: r.v, salt: saltB64, iv: r.iv, ct: r.ct });
      return decryptStr(r.iv, r.ct).then(function (s) { hydrate(s); }, function () {
        // kunci ingatan salah (passphrase sudah diganti di perangkat lain?)
        key = null; try { localStorage.removeItem('gf_remember'); } catch (e) {}
        return unlockLoop();
      });
    });
  }

  /* ---------- boot offline: buka salinan terakhir dari perangkat ---------- */
  function offlineOpen() {
    var c = readCache();
    if (!c) return fail('Tidak bisa menghubungi server.\nPeriksa koneksi internet, lalu buka lagi.');
    if (!saltB64) saltB64 = c.salt;
    ver = c.v || 0;
    var p = key ? Promise.resolve() : askPass('Sedang offline — membuka salinan terakhir dari perangkat ini.');
    p.then(function () { return decryptStr(c.iv, c.ct); })
      .then(function (s) { hydrate(s); })
      .catch(function () {
        key = null; try { localStorage.removeItem('gf_remember'); } catch (e) {}
        offlineUnlockLoop(c);
      });
  }
  function offlineUnlockLoop(c) {
    askPass('Passphrase salah — coba lagi.').then(function () {
      return decryptStr(c.iv, c.ct).then(function (s) { hydrate(s); }, function () { return offlineUnlockLoop(c); });
    });
  }

  var hydrated = false, hydrateCb = null;
  function hydrate(json) {
    hydrated = true;
    flushQueue();
    if (hydrateCb) { var cb = hydrateCb; hydrateCb = null; cb(json); }
    resolveReady();
  }
  function onHydrate(cb) { if (hydrated) cb(lastState); else hydrateCb = cb; }
  var lastState = '';

  /* ---------- simpan: buang kunci UI sesaat sebelum enkripsi ---------- */
  var STRIP = { syncStatus: 1, toast: 1, toastUndo: 1, animTotal: 1, draft: 1, modalType: 1, screen: 1, aturOpen: 1, pinEntry: 1, pinError: 1, pinPrompt: 1, pinStage: 1, pinTmp: 1, pinPurpose: 1, locked: 1, hidden: 1, recovery: 1, bankSearch: 1, actFilter: 1, actSearch: 1, histTab: 1, homeBreakdown: 1, calYear: 1 };
  function cleanState(json) {
    try {
      var st = JSON.parse(json), out = {};
      for (var k in st) if (!STRIP[k]) out[k] = st[k];
      return JSON.stringify(out);
    } catch (e) { return json; }
  }

  /* ---------- shim google.script.run (rantai dengan handler) ---------- */
  function chain(ok, failh) {
    return {
      withSuccessHandler: function (f) { return chain(f, failh); },
      withFailureHandler: function (f) { return chain(ok, f); },
      getState: function () {
        onHydrate(function (json) { try { (ok || function () {})(json); } catch (e) {} });
        ready.catch(function () {});
      },
      saveState: function (json) {
        lastState = json;
        if (!key) return; // belum terhidrasi — app lokal dulu
        var clean = cleanState(json);
        encryptStr(clean).then(function (e) {
          return api({ action: 'save', key: AK, base: ver, iv: e.iv, ct: e.ct, salt: saltB64 })
            .then(function (r) {
              if (r.conflict) {
                alert('Data di perangkat lain lebih baru.\nMemuat ulang agar tidak ada yang hilang…');
                location.reload(); return;
              }
              if (r.err === 'auth') { alert('Access Key ditolak server.'); return; }
              if (r.err) throw 0;
              ver = r.v; flushQueue();
              try { (ok || function () {})(true); } catch (e2) {}
            });
        }).catch(function () {
          // offline → antre terenkripsi, flush saat online
          encryptStr(clean).then(function (e2) {
            var q = queue(); q.push({ base: ver, iv: e2.iv, ct: e2.ct }); setQueue(q);
            try { (ok || function () {})(true); } catch (e3) {}
          });
        });
      }
    };
  }
  window.google = { script: { run: chain(null, null) } };

  if (!API) needInstall(); else boot();
})();
