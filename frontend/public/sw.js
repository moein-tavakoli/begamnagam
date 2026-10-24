/* Phase-one PWA foundation. Version this when the public fallback changes.
 * No private pages, API/RSC responses or requests are ever persisted/replayed.
 * No skipWaiting/reload: an update waits until existing clients close.
 */
const CACHE = 'begamnagam-public-foundation-v1';
const PUBLIC = ['/offline.html', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC)));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith('begamnagam-public-') && key !== CACHE)
    .map(key => caches.delete(key)))));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || request.method !== 'GET') return;
  // This allowlist is exact. A query or private route never enters CacheStorage.
  if (PUBLIC.includes(url.pathname) && !url.search) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(request)).then(hit => hit || fetch(request)));
    return;
  }
  // Navigation is network-only. Offline always gets the anonymous static page,
  // never the previous user's HTML. API and RSC fetches fall through untouched.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => {
      const cached = await caches.open(CACHE).then(cache => cache.match('/offline.html'));
      return cached || new Response('اتصال اینترنت برقرار نیست.', {
        status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}
      });
    }));
  }
});
