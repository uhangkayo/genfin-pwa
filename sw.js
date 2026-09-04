/* GenFin Service Worker v2 — app shell offline-first
 * v2: network-first untuk navigasi & gf-bridge.js agar update bugfix
 *     langsung sampai ke pengguna (asset besar tetap cache-first). */
var CACHE = 'genfin-v5';
var CORE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './gf-bridge.js',
  './assets/react.js',
  './assets/react-dom.js',
  './assets/dc-runtime.js',
  './apple-touch-icon.png',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return; // API GAS lewat langsung

  // network-first: halaman & bridge (update segera efektif)
  if (e.request.mode === 'navigate' || url.pathname.indexOf('gf-bridge.js') !== -1) {
    e.respondWith(
      fetch(e.request).then(function (res) {
        if (res && res.ok) { var cp = res.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, cp); }); }
        return res;
      }).catch(function () {
        return caches.match(e.request, { ignoreSearch: true }).then(function (hit) { return hit || Response.error(); });
      })
    );
    return;
  }

  // asset besar: stale-while-revalidate
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(function (hit) {
      var net = fetch(e.request).then(function (res) {
        if (res && res.ok) { var cp = res.clone(); caches.open(CACHE).then(function (c) { c.put(e.request, cp); }); }
        return res;
      }).catch(function () {
        return hit || (e.request.mode === 'navigate' ? caches.match('./index.html') : Response.error());
      });
      return hit || net;
    })
  );
});
