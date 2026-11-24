/* registro-comidas · service worker
   - Interfaz (HTML/CSS/JS/iconos): cache-first → abre al instante y sin conexión.
   - Datos (config.json y data/*): red primero, copia en caché como respaldo offline.
   Sube VERSION cuando cambies index.html, app.js o styles.css. */
var VERSION = 'rc-1.0.0';
var SHELL = ['./', 'index.html', 'app.js', 'styles.css', 'manifest.webmanifest',
  'icons/icon-192.png', 'icons/icon-512.png', 'fonts/Sora-latin.woff2'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) {
    // los datos se precargan sin bloquear la instalación si alguno falta (p. ej. proyecto recién creado)
    var datos = ['config.json', 'data/indice.json'].map(function (u) { return c.add(u).catch(function () {}); });
    return Promise.all([c.addAll(SHELL)].concat(datos));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  var esDato = url.pathname.indexOf('/data/') >= 0 || url.pathname.endsWith('/config.json');
  if (esDato) {
    e.respondWith(fetch(e.request).then(function (r) {
      if (r.ok) { var copia = r.clone(); caches.open(VERSION).then(function (c) { c.put(e.request, copia); }); }
      return r;
    }).catch(function () { return caches.match(e.request); }));
  } else {
    e.respondWith(caches.match(e.request).then(function (r) { return r || fetch(e.request); }));
  }
});
