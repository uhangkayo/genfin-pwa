/**
 * ============================================================
 *  GENFIN API v2 — JSON API terenkripsi untuk Google Sheets
 * ============================================================
 *  PERBEDAAN DARI VERSI LAMA:
 *   - doPost murni JSON API (dipanggil PWA via fetch) — bukan UI.
 *   - Server TIDAK PERNAH melihat plaintext: hanya menerima
 *     ciphertext AES-GCM dari perangkat klien.
 *   - Access Key (secret keluarga) wajib di setiap request.
 *   - Versioning: penulisan dengan versi basi DITOLAK (anti
 *     last-write-wins), snapshot 10 versi terakhir di tab _HIST.
 *   - Tab mirror (Pos/Bank/Ledger dst) tidak dibangun ulang —
 *     server buta terhadap isi data (konsekuensi E2E).
 *
 *  SETUP (5 menit, sekali saja):
 *   1. Buka Extensions ▸ Apps Script pada Spreadsheet GenFin.
 *   2. GANTI SELURUH isi Code.gs dengan file ini. Simpan.
 *   3. Jalankan fungsi setupGenFin() sekali (tombol Run).
 *      → Salin ACCESS KEY dari Execution log (berikan ke setiap
 *        perangkat keluarga, sekali saja saat pertama buka PWA).
 *   4. Deploy ▸ New deployment ▸ Web app:
 *        Execute as: Me    |    Who has access: Anyone
 *      → Salin URL /exec, buka PWA dengan tambahan:
 *        https://<host>/?api=<URL exec yang di-encode>
 *      (cukup sekali — URL tersimpan otomatis di perangkat).
 *
 *  MIGRASI DATA LAMA: otomatis. Jika _DB berisi plaintext lama,
 *  PWA akan meminta passphrase baru, lalu menulis ulang _DB
 *  sebagai ciphertext versi 1.
 * ============================================================
 */

var DB = '_DB';      // penyimpan otoritatif (terenkripsi, tersembunyi)
var HIST = '_HIST';  // snapshot 10 versi terakhir (terenkripsi)
var AUDIT = '_AUDIT';// log aksi server-side (tanpa isi data)
var CHUNK = 40000;   // < 50.000 karakter per sel (batas Sheets)

function _ss() { return SpreadsheetApp.getActiveSpreadsheet(); }

function _sh(name) {
  var ss = _ss(), sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); if (name === DB) { try { sh.hideSheet(); } catch (e) {} } }
  return sh;
}

/** Jalankan SEKALI dari editor. Cetak ACCESS KEY di log. */
function setupGenFin() {
  var k = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
  PropertiesService.getScriptProperties().setProperty('GF_KEY', k);
  var h = _sh(HIST); if (h.getLastRow() === 0) h.getRange(1, 1, 1, 5).setValues([['Waktu', 'Versi', 'Salt', 'IV', 'CT']]).setFontWeight('bold');
  var a = _sh(AUDIT); if (a.getLastRow() === 0) a.getRange(1, 1, 1, 4).setValues([['Waktu', 'Aksi', 'Versi', 'Catatan']]).setFontWeight('bold');
  _audit('SETUP', 0, 'API v2 aktif');
  Logger.log('==================================================\n' +
    ' ACCESS KEY KELUARGA (simpan rahasia, perangkat baru perlu ini):\n ' + k + '\n' +
    '==================================================');
}

function _key() { return PropertiesService.getScriptProperties().getProperty('GF_KEY') || ''; }

function _gate(req) {
  var ok = !!_key() && String(req.key || '') === _key();
  if (!ok) {
    var c = CacheService.getScriptCache(), f = Number(c.get('gf_fail') || 0) + 1;
    c.put('gf_fail', String(f), 900); // 15 menit
    _audit('AUTH_FAIL', 0, 'percobaan ke-' + f);
  }
  return ok;
}

function _locked() {
  var f = Number(CacheService.getScriptCache().get('gf_fail') || 0);
  return f > 15; // brute-force guard
}

function _read() {
  var sh = _ss().getSheetByName(DB);
  if (!sh || sh.getLastRow() < 1) return null;
  var n = sh.getLastRow();
  var vals = sh.getRange(1, 1, n, 2).getValues();
  var a = '';
  for (var i = 0; i < n; i++) a += String(vals[i][0] || '');
  if (a.indexOf('{"enc"') === 0) {
    var env; try { env = JSON.parse(a); } catch (e) { return null; }
    var ct = '';
    for (var j = 0; j < (env.chunks || 0) && j < n; j++) ct += String(vals[j][1] || '');
    return { enc: true, v: env.v, salt: env.salt, iv: env.iv, ct: ct };
  }
  // format lama: plaintext ber-chunk di kolom A → kandidat migrasi
  return { enc: false, legacy: a };
}

function _chunks(s) { var out = []; for (var i = 0; i < s.length; i += CHUNK) out.push(s.substr(i, CHUNK)); return out; }

function _write(env, ctChunks) {
  var lock = LockService.getScriptLock();
  try { lock.waitLock(20000); } catch (e) {}
  try {
    var sh = _sh(DB);
    sh.clearContents();
    var rows = [];
    var maxR = Math.max(1, ctChunks.length);
    for (var i = 0; i < maxR; i++) {
      rows.push([i === 0 ? JSON.stringify(env) : '', ctChunks[i] || '']);
    }
    sh.getRange(1, 1, rows.length, 2).setValues(rows);
  } finally { try { lock.releaseLock(); } catch (e) {} }
}

function _hist(env, ct) {
  try {
    var sh = _sh(HIST);
    var ch = _chunks(ct);
    sh.appendRow([new Date(), env.v, env.salt, env.iv, ch[0] || '', ch[1] || '', ch[2] || '']);
    if (sh.getLastRow() > 11) sh.deleteRows(12, sh.getLastRow() - 11);
  } catch (e) {}
}

function _audit(action, v, note) {
  try { _sh(AUDIT).appendRow([new Date(), action, v || 0, note || '']); } catch (e) {}
}

function doPost(e) {
  var req = {};
  try { req = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (err) {}
  function out(o) {
    return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
  }

  if (_locked()) return out({ err: 'rate' });
  if (!_gate(req)) return out({ err: 'auth' });

  if (req.action === 'meta') {
    var d = _read();
    return out({
      ok: true,
      hasEnc: !!(d && d.enc),
      hasLegacy: !!(d && !d.enc && d.legacy && d.legacy.length),
      salt: (d && d.enc) ? d.salt : null,
      v: (d && d.enc) ? d.v : 0
    });
  }

  if (req.action === 'get') {
    var g = _read();
    _audit('GET', g && g.enc ? g.v : 0, '');
    if (g && g.enc) return out({ enc: true, v: g.v, iv: g.iv, ct: g.ct });
    return out({ enc: false, legacy: g ? g.legacy : '' });
  }

  if (req.action === 'save') {
    var s = _read();
    var base = Number(req.base || 0);
    var vNow = (s && s.enc) ? s.v : 0;
    if (base !== vNow) { _audit('CONFLICT', vNow, 'base=' + base); return out({ conflict: true, v: vNow }); }
    var ct = String(req.ct || ''), iv = String(req.iv || ''), salt = String(req.salt || '');
    if (!ct || !iv || !salt) return out({ err: 'bad' });
    var ch = _chunks(ct);
    var env = { enc: 1, v: vNow + 1, salt: salt, iv: iv, chunks: ch.length };
    _write(env, ch);
    _hist(env, ct);
    _audit('SAVE', env.v, ch.length + ' chunk');
    return out({ ok: true, v: env.v });
  }

  return out({ err: 'unknown' });
}

function doGet() {
  return ContentService.createTextOutput(JSON.stringify({ app: 'GenFin API', v: 2 }))
    .setMimeType(ContentService.MimeType.JSON);
}
