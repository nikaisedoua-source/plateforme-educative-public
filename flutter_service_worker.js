// Remplace l'ancien « service worker » de Flutter sur les appareils qui l'avaient installé (Android surtout) :
// vide les copies du site gardées hors ligne, se désinstalle, puis recharge la page sur la version en ligne.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
    await self.registration.unregister();
    const pages = await self.clients.matchAll({ type: 'window' });
    pages.forEach((page) => page.navigate(page.url));
  })());
});
