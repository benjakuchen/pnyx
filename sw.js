/* Pnyx · Service Worker mínimo
   Objetivo: habilitar la instalación como PWA sin cachear la app, para que
   SIEMPRE se cargue la última versión (evita el problema de versiones viejas
   pegadas en caché). Solo intercepta para dar un mensaje si no hay conexión. */

self.addEventListener('install', function(e){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });

self.addEventListener('fetch', function(e){
  // Estrategia: siempre red primero. Si falla (sin conexión) y es una
  // navegación, mostramos un aviso simple. No guardamos nada en caché.
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(function(){
        return new Response(
          '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">' +
          '<meta name="viewport" content="width=device-width,initial-scale=1">' +
          '<title>Pnyx · sin conexión</title></head>' +
          '<body style="font-family:sans-serif;text-align:center;padding:60px 24px;color:#1a1d24;background:#f4f7fb">' +
          '<div style="font-size:44px">📡</div>' +
          '<h1 style="font-size:20px">Sin conexión</h1>' +
          '<p style="color:#5b6472">Necesitás internet para usar Pnyx. Volvé a intentar cuando tengas señal.</p>' +
          '<button onclick="location.reload()" style="margin-top:12px;padding:12px 20px;border:none;border-radius:10px;background:#1C5BAE;color:#fff;font-size:15px;font-weight:700">Reintentar</button>' +
          '</body></html>',
          { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
      })
    );
  }
});
