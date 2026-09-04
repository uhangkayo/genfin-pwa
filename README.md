# GenFin PWA — Cash Flow Keluarga (E2EE)

Frontend PWA + backend Apps Script. Data tersimpan di Google Sheet sebagai
**ciphertext AES-256-GCM** — plaintext tidak pernah meninggalkan perangkat.

## Struktur
- `index.html` — aplikasi (UI asli GenFin, tanpa perubahan logika)
- `gf-bridge.js` — jembatan: E2EE (PBKDF2 210k + AES-GCM) + API fetch + antrian offline + shim `google.script.run`
- `sw.js`, `manifest.webmanifest`, `*-icon*.png` — PWA (installable, offline, ikon iOS/Android)
- `assets/` — React 18.3.1, ReactDOM, dc-runtime (bundle asli)
- `Code.gs` — backend Apps Script API v2 (access key + versioning + snapshot)
- `tools/mock_server.py` — server mock untuk QA lokal

## Setup backend (5 menit)
1. Buka Spreadsheet GenFin → Extensions ▸ Apps Script.
2. Ganti seluruh isi `Code.gs` dengan `Code.gs` repo ini. Simpan.
3. Jalankan `setupGenFin()` sekali → salin **ACCESS KEY** dari log.
4. Deploy ▸ New deployment ▸ Web app — *Execute as: Me*, *Who has access: Anyone* → salin URL `/exec`.

## Pasang di perangkat
Buka PWA sekali dengan parameter:
```
https://uhangkayo.github.io/genfin-pwa/?api=<URL /exec di-URL-encode>
```
Masukkan Access Key → buat passphrase (min. 10 karakter) → selesai.
Data lama plaintext dimigrasi otomatis menjadi terenkripsi.

## Keamanan
- Enkripsi ujung-ke-ujung: kunci diturunkan di perangkat (PBKDF2-SHA256 210.000 iterasi), server hanya menyimpan ciphertext.
- Access Key keluarga + rate-limit gagal otomatis (15 menit lock).
- Optimistic concurrency: penimpaan antar-perangkat ditolak, bukan diam-diam.
- Snapshot 10 versi terakhir (tab `_HIST`) + audit log (`_AUDIT`).
- Jika lupa passphrase: data **tidak bisa** dipulihkan — simpan passphrase di tempat aman.
