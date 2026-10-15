'use strict';
const CACHE='ajou-notices-__VERSION__',BASE=new URL('./',self.location.href);
const FILES=['./','index.html','styles.css','notice.css','app.js','core.js','data.js','notices.json','manifest.webmanifest','favicon.svg','icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png'];
self.addEventListener('install',event=>event.waitUntil((async()=>{const cache=await caches.open(CACHE);await cache.addAll(FILES.map(x=>new URL(x,BASE).href));await self.skipWaiting();})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const key of await caches.keys())if(key.startsWith('ajou-notices-')&&key!==CACHE)await caches.delete(key);await self.clients.claim();})()));
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==BASE.origin||!url.pathname.startsWith(BASE.pathname))return;
  const relative=url.pathname.slice(BASE.pathname.length)||'index.html';
  if(!FILES.includes(relative)&&!event.request.mode.includes('navigate'))return;
  // Network first for every resource: an installed app must not pin old notice data.
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request);
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }catch(error){
      const cached=await cache.match(event.request,{ignoreSearch:true});
      if(cached)return cached;
      if(event.request.mode==='navigate')return (await cache.match(new URL('index.html',BASE).href))||Response.error();
      throw error;
    }
  })());
});
