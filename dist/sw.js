'use strict';
importScripts('core.js');
const CACHE='ajou-notices-5476daa4977c',BASE=new URL('./',self.location.href);
const FILES=['./','index.html','styles.css','notice.css','app.js','core.js','appearance.js','background.js','contrast.js','data.js','notices.json','manifest.webmanifest','favicon.svg','icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png','notices.ics','assets/default-background.svg'];
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
      const response=await fetch(event.request,{cache:'no-store'});
      // A refresh query must update the canonical snapshot used during offline reloads.
      if(response.ok){
        if(relative==='notices.json'){
          const archive=await response.clone().json().catch(()=>null);
          if(self.NoticeCore.validArchive(archive)){
            await cache.put(new URL(relative,BASE).href,response.clone());
            // Keep the executable bootstrap in sync with a manually refreshed snapshot.
            await cache.put(new URL('data.js',BASE).href,new Response('window.AJOU_NOTICES = '+JSON.stringify(archive)+';',{
              headers:{'Content-Type':'text/javascript; charset=utf-8'}
            }));
          }
        }else await cache.put(new URL(relative,BASE).href,response.clone());
      }
      return response;
    }catch(error){
      const cached=await cache.match(event.request,{ignoreSearch:true});
      if(cached)return cached;
      if(event.request.mode==='navigate')return (await cache.match(new URL('index.html',BASE).href))||Response.error();
      throw error;
    }
  })());
});
