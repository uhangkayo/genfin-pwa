#!/usr/bin/env python3
"""Mock server QA GenFin — meniru API Apps Script Code.gs v2.1 secara lokal.
Pakai: python3 tools/mock_server.py [port]  →  buka http://localhost:8123/?api=http%3A%2F%2Flocalhost%3A8123%2Fexec
Access key mock: MOCKKEY-MOCKKEY-MOCKKEY-1234 (min 16 karakter).
CATATAN: jangan pakai port 8000 (dipakai idx_dashboard API).
"""
import json, os, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STORE = os.path.join(ROOT, '.mock-store.json')
LEGACY_SEED = os.path.join(ROOT, '.mock-legacy.json')
KEY = 'MOCKKEY-MOCKKEY-MOCKKEY-1234'

class H(SimpleHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')

    def _json(self, o):
        b = json.dumps(o).encode()
        self.send_response(200); self._cors()
        self.send_header('Content-Length', str(len(b))); self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith('/exec'):
            self._json({'app': 'GenFin API', 'v': 2, 'setup': True})
        else:
            super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/exec'):
            self.send_error(404); return
        ln = int(self.headers.get('Content-Length', 0))
        req = json.loads(self.rfile.read(ln) or b'{}')
        if os.path.exists(STORE):
            st = json.load(open(STORE))
        else:
            legacy = open(LEGACY_SEED).read() if os.path.exists(LEGACY_SEED) else ''
            st = {'enc': False, 'legacy': legacy}

        # sendkey = pre-auth (hanya mengirim key ke "email pemilik")
        if req.get('action') == 'sendkey':
            self._json({'ok': True}); return

        if (req.get('key') or '').strip() != KEY:
            self._json({'err': 'auth'}); return
        a = req.get('action')
        if a == 'meta':
            self._json({'ok': True, 'hasEnc': st['enc'],
                        'hasLegacy': (not st['enc'] and bool(st['legacy'])),
                        'salt': st.get('salt'), 'v': st.get('v', 0)})
        elif a == 'get':
            if st['enc']:
                self._json({'enc': True, 'v': st['v'], 'iv': st['iv'], 'ct': st['ct']})
            else:
                self._json({'enc': False, 'legacy': st['legacy']})
        elif a == 'save':
            cur = st.get('v', 0) if st['enc'] else 0
            if req.get('base', 0) != cur:
                self._json({'conflict': True, 'v': cur}); return
            st = {'enc': True, 'v': cur + 1, 'salt': req['salt'], 'iv': req['iv'], 'ct': req['ct']}
            json.dump(st, open(STORE, 'w'))
            self._json({'ok': True, 'v': st['v']})
        else:
            self._json({'err': 'unknown'})

    def log_message(self, *a):
        pass

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    os.chdir(ROOT)
    print(f'Mock GenFin API + static: http://localhost:{port}/  |  exec: /exec  |  key: {KEY}')
    HTTPServer(('127.0.0.1', port), H).serve_forever()
