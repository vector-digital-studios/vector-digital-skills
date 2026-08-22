/* V Drop — service worker mínimo: hace la PWA instalable en escritorio
   y cachea el shell para que abra sin internet. La API JAMÁS se cachea. */
const CACHE = "vdrop-v2";
const STATIC = [
  "/",
  "/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/logo-vdrop.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(STATIC))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // nunca interceptar la API ni peticiones que no sean GET
  if (url.pathname.startsWith("/api/") || e.request.method !== "GET") return;

  // navegación: red primero (shell siempre fresco), cache como respaldo offline
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request).then((resp) => {
        if (resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        }
        return resp;
      }).catch(() => caches.match("/"))
    );
    return;
  }

  // estáticos: cache primero
  e.respondWith(
    caches.match(e.request).then((hit) => {
      if (hit) return hit;
      return fetch(e.request).then((resp) => {
        if (resp.ok && url.origin === self.location.origin) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        }
        return resp;
      }).catch(() => caches.match("/"));
    })
  );
});
