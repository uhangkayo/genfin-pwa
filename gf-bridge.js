/* ============================================================
 * GenFin Bridge — E2EE (AES-GCM 256 + PBKDF2) + Apps Script API
 * Menggantikan google.script.run dengan fetch + enkripsi penuh.
 * Sheet hanya pernah menerima ciphertext. Plaintext tidak pernah
 * meninggalkan perangkat.
 * ============================================================ */
(function () {
  'use strict';

  /* ---------- config: pasang API lewat ?api=<URL exec> sekali saja ---------- */
  try {
    var u = new URLSearchParams(location.search).get('api');
    if (u) { localStorage.setItem('gf_api_url', u); history.replaceState(null, '', location.pathname); }
  } catch (e) {}
  var API = null;
  try { API = localStorage.getItem('gf_api_url'); } catch (e) {}
  if (!API) return; // mode lokal murni (localStorage) — PWA tetap jalan

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

  /* ---------- state ---------- */
  var key = null, saltB64 = null, ver = 0, AK = null;
  try { AK = localStorage.getItem('gf_ak'); } catch (e) {}
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

  /* ---------- kunci yang diingat perangkat (opsional, 7 hari) ---------- */
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

  /* ---------- gerbang UI (unlock / setup / access key) ---------- */
  var CSS =
    '#gf-gate{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;' +
    'background:linear-gradient(160deg,#0b3d2e 0%,#0e5941 60%,#12805a 100%);font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;' +
    '-webkit-backdrop-filter:blur(6px);}' +
    '#gf-gate .gf-card{background:rgba(255,255,255,.98);border-radius:20px;padding:26px 22px;width:min(88vw,340px);box-shadow:0 18px 50px rgba(0,0,0,.4);}' +
    '#gf-gate .gf-logo{width:54px;height:54px;border-radius:14px;background:linear-gradient(150deg,#0b3d2e,#16a34a);color:#fbbf24;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;margin:0 auto 10px;}' +
    '#gf-gate h1{font-size:17px;margin:2px 0 2px;text-align:center;color:#0b3d2e;}' +
    '#gf-gate p{font-size:12.5px;color:#6b7280;text-align:center;margin:0 0 14px;line-height:1.45;}' +
    '#gf-gate input{width:100%;box-sizing:border-box;border:1.6px solid #d1d5db;border-radius:11px;padding:11px 12px;font-size:15px;margin-bottom:10px;}' +
    '#gf-gate input:focus{border-color:#16a34a;outline:none;}' +
    '#gf-gate button{width:100%;border:0;border-radius:11px;padding:12px;font-size:15px;font-weight:700;color:#fff;background:linear-gradient(150deg,#0b3d2e,#16a34a);cursor:pointer;}' +
    '#gf-gate button:active{opacity:.85;}' +
    '#gf-gate .gf-err{color:#dc2626;font-size:12.5px;text-align:center;margin:-4px 0 8px;min-height:15px;}' +
    '#gf-gate label{display:flex;gap:8px;align-items:center;font-size:12px;color:#6b7280;margin:-4px 0 10px;}' +
    '#gf-gate .gf-badge{position:fixed;bottom:10px;left:50%;transform:translateX(-50%);color:rgba(255,255,255,.75);font-size:10.5px;}';
  function gate(opts) {
    // opts: {title, sub, fields:[{id,type,placeholder,label?}], button, check?}
    return new Promise(function (resolve) {
      var st = document.createElement('style'); st.textContent = CSS; document.documentElement.appendChild(st);
      var d = document.createElement('div'); d.id = 'gf-gate';
      var inputs = opts.fields.map(function (f) {
        return (f.label ? '<label><input type="checkbox" id="gf-f-' + f.id + '-ck" style="width:auto;margin:0"> ' + f.label + '</label>' : '') +
          '<input id="gf-f-' + f.id + '" type="' + (f.type || 'text') + '" placeholder="' + f.placeholder + '" autocomplete="off">' ;
      }).join('');
      d.innerHTML = '<div class="gf-card"><div class="gf-logo">G</div><h1>' + opts.title + '</h1><p>' + opts.sub + '</p>' +
        '<div class="gf-err" id="gf-err"></div>' + inputs +
        '<button id="gf-ok">' + opts.button + '</button></div>' +
        '<div class="gf-badge">GenFin • terenkripsi ujung-ke-ujung</div>';
      document.documentElement.appendChild(d);
      var first = document.getElementById('gf-f-' + opts.fields[0].id); if (first) first.focus();
      function submit() {
        var vals = {};
        opts.fields.forEach(function (f) {
          vals[f.id] = (document.getElementById('gf-f-' + f.id) || {}).value || '';
          var ck = document.getElementById('gf-f-' + f.id + '-ck');
          vals[f.id + '_ck'] = ck ? ck.checked : false;
        });
        var bad = opts.check ? opts.check(vals) : null;
        if (bad) { document.getElementById('gf-err').textContent = bad; return; }
        d.remove(); resolve(vals);
      }
      document.getElementById('gf-ok').addEventListener('click', submit);
      d.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    });
  }

  /* ---------- bootstrap ---------- */
  function boot(retry) {
    var rem = loadRemember();
    var p = (rem && !retry)
      ? rem.then(function (k) { key = k; return api({ action: 'meta', key: AK }); })
      : api({ action: 'meta', key: AK });
    p.then(function (m) {
      if (m.err === 'rate') return fail('Terlalu banyak percobaan gagal. Coba lagi 15 menit.');
      if (m.err === 'auth') return askKey();
      if (!m.hasEnc) {
        if (m.hasLegacy) return migrate(m);       // data lama plaintext → enkripsi sekarang
        return freshInstall();                     // Sheet kosong → set passphrase baru
      }
      saltB64 = m.salt;
      if (key) return fetchState();                // kunci hasil "ingat perangkat" — langsung
      return unlock();
    }).catch(function () { fail('Tidak bisa menghubungi server. Periksa koneksi, lalu buka ulang.'); });
  }

  function askKey() {
    return gate({
      title: 'GenFin', sub: 'Masukkan Access Key keluarga untuk perangkat ini.',
      fields: [{ id: 'ak', placeholder: 'Access Key', type: 'password' }],
      button: 'Buka',
      check: function (v) { return v.ak.length < 16 ? 'Access Key terlalu pendek.' : null; }
    }).then(function (v) {
      AK = v.ak; try { localStorage.setItem('gf_ak', AK); } catch (e) {}
      return boot();
    });
  }

  function unlock(retryMsg) {
    return gate({
      title: 'GenFin terkunci',
      sub: (retryMsg || 'Masukkan passphrase untuk mendekripsi data.'),
      fields: [{ id: 'pass', placeholder: 'Passphrase', type: 'password', label: 'Tetap terbuka di perangkat ini (7 hari)' }],
      button: 'Buka Kunci',
      check: function (v) { return v.pass.length < 4 ? 'Isi passphrase.' : null; }
    }).then(function (v) {
      return derive(v.pass, saltB64, v.pass_ck).then(function (k) { key = k; if (v.pass_ck) saveRemember(); })
        .then(fetchState)
        .catch(function () { return unlock('Passphrase salah — coba lagi.'); });
    });
  }

  function newPass(sub) {
    return gate({
      title: 'Buat Passphrase Data', sub: sub,
      fields: [
        { id: 'p1', placeholder: 'Passphrase (min. 10 karakter)', type: 'password' },
        { id: 'p2', placeholder: 'Ulangi passphrase', type: 'password', label: 'Tetap terbuka di perangkat ini (7 hari)' }
      ],
      button: 'Enkripsi & Simpan',
      check: function (v) {
        if (v.p1.length < 10) return 'Minimal 10 karakter — ini yang melindungi data miliaran Anda.';
        if (v.p1 !== v.p2) return 'Kedua isian belum sama.';
        return null;
      }
    }).then(function (v) {
      saltB64 = rndB64(16);
      return derive(v.p1, saltB64, v.p2_ck).then(function (k) { key = k; if (v.p2_ck) saveRemember(); });
    });
  }

  function migrate(m) {
    return newPass('Data lama akan dienkripsi sekarang. Passphrase INI kunci baru Anda — JANGAN lupa, tidak ada reset.')
      .then(function () {
        return api({ action: 'get', key: AK }).then(function (r) {
          if (!r.legacy) return '';
          // migrasi: simpan ulang sebagai ciphertext versi 1
          return encryptStr(r.legacy).then(function (e) {
            return api({ action: 'save', key: AK, base: 0, iv: e.iv, ct: e.ct, salt: saltB64 })
              .then(function (res) { ver = res.v || 1; }); // sinkronkan versi agar save app berikutnya tidak false-conflict
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
      return decryptStr(r.iv, r.ct).then(function (s) { hydrate(s); })
        .catch(function () { // kunci ingatan salah (passphrase sudah diganti?)
          key = null; try { localStorage.removeItem('gf_remember'); } catch (e) {}
          return unlock('Passphrase salah — coba lagi.');
        });
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

  function fail(msg) { alert(msg); }

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

  boot();
})();
