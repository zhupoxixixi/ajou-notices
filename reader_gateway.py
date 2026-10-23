"""Fetch original public HTML through Reader without forwarding AI credentials."""
import threading
import time
import base64
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs,urlsplit

import requests
from bs4 import BeautifulSoup

from crawl import BOARDS
from source_gateway import GatewayError

_CACHE={}
_SHOTS={}
_LOCK=threading.Lock()
_NEXT_REQUEST=0.0
INTERVAL=3.4  # Stay below Reader's anonymous 20 requests/minute per IP.
READER='https://r.jina.ai/'

def allowed_page(url):
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):return False
        if p.hostname=='taekwondo.jbcomz.co.kr':return p.path=='/' and not p.query
        if p.hostname=='library.ajou.ac.kr' and p.path.startswith('/guide/bulletins/notice/'):
            return p.path.rsplit('/',1)[-1].isdigit() and not p.query
        if not any((p.hostname,p.path)==(urlsplit(v[1]).hostname,urlsplit(v[1]).path) for v in BOARDS.values()):return False
        q=parse_qs(p.query)
        if q.get('mode',[''])[0]=='view':return len(q.get('articleNo',[]))==1 and q['articleNo'][0].isdigit()
        return q.get('mode',[''])[0] in ('','list')
    except (ValueError,TypeError):return False

def _pace():
    global _NEXT_REQUEST
    with _LOCK:
        start=max(time.monotonic(),_NEXT_REQUEST)
        _NEXT_REQUEST=start+INTERVAL
    delay=start-time.monotonic()
    if delay>0:time.sleep(delay)

def _read(url):
    if not allowed_page(url):raise GatewayError('Reader URL is outside the configured public-source allowlist')
    for attempt in range(3):
        _pace()
        try:
            detail=parse_qs(urlsplit(url).query).get('mode',[''])[0]=='view' or '/guide/bulletins/notice/' in urlsplit(url).path
            headers={'Accept':'application/json','X-Respond-With':'pageshot' if detail else 'html','X-No-Cache':'true','X-Timeout':'30'}
            if not detail:headers['X-Engine']='direct'
            response=requests.get(READER+url,headers=headers,timeout=(10,50),allow_redirects=False)
        except requests.RequestException as exc:
            if attempt<2:time.sleep(2**attempt);continue
            raise GatewayError('Reader network error: '+type(exc).__name__) from None
        # Reader can transiently report 422 while the public origin is reachable.
        if response.status_code in (422,429,500,502,503,504) and attempt<2:
            try:delay=min(30,max(3,float(response.headers.get('Retry-After','10'))))
            except ValueError:delay=10
            time.sleep(delay);continue
        if response.status_code!=200:raise GatewayError('Reader HTTP '+str(response.status_code))
        if len(response.content)>4*1024*1024:raise GatewayError('Reader HTML exceeds size limit')
        try:payload=response.json();page=payload['data']
        except (ValueError,KeyError,TypeError):raise GatewayError('Reader response has no structured page') from None
        if not isinstance(payload,dict) or not isinstance(page,dict):raise GatewayError('Reader response has an invalid page shape')
        if payload.get('code')!=200 or page.get('httpStatus')!=200:raise GatewayError('Reader could not retrieve the official page successfully')
        if page.get('url')!=url:raise GatewayError('Reader returned a different source URL')
        html=page.get('html')
        if not isinstance(html,str) or not html.strip():raise GatewayError('Reader returned no original HTML')
        soup=BeautifulSoup(html,'html.parser')
        if not soup.find(['html','table','body','div']):raise GatewayError('Reader did not return a usable HTML document')
        if detail and isinstance(page.get('pageshotUrl'),str):
            with _LOCK:_SHOTS[url]=page['pageshotUrl']
        return html
    raise GatewayError('Reader retries exhausted')

def fetch_pages(urls):
    """Fetch in three paced lanes; retain per-URL errors for normal preservation."""
    unique=list(dict.fromkeys(urls))
    with _LOCK:todo=[url for url in unique if url not in _CACHE]
    def read_one(url):
        try:value=_read(url)
        except GatewayError as exc:value=exc
        with _LOCK:_CACHE[url]=value
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(read_one,todo))
    with _LOCK:return {url:_CACHE[url] for url in unique}

def fetch_html(url):
    result=fetch_pages([url])[url]
    if isinstance(result,GatewayError):raise result
    return result

def _download_snapshot(url):
    for attempt in range(3):
        try:response=requests.get(url,timeout=(10,40),allow_redirects=False)
        except requests.RequestException as exc:
            if attempt<2:time.sleep(2**attempt);continue
            raise GatewayError('Reader image network error: '+type(exc).__name__) from None
        if response.status_code in (429,500,502,503,504) and attempt<2:
            try:delay=min(30,max(3,float(response.headers.get('Retry-After','10'))))
            except ValueError:delay=10
            time.sleep(delay);continue
        if response.status_code!=200 or not response.headers.get('Content-Type','').startswith('image/'):
            raise GatewayError('Reader full-page image could not be downloaded (HTTP '+str(response.status_code)+')')
        if len(response.content)>16*1024*1024:raise GatewayError('Reader full-page image exceeds size limit')
        return response.content

def snapshot_images(url):
    """Return every pixel of the official page in legible, overlapping tiles."""
    fetch_html(url)
    with _LOCK:shot=_SHOTS.get(url,'')
    if not shot:
        # HTML can arrive before Reader finishes producing its requested
        # pageshot. Discard that partial response and make one bounded refresh.
        with _LOCK:
            _CACHE.pop(url,None);_SHOTS.pop(url,None)
        try:fetch_html(url)
        except GatewayError:
            with _LOCK:
                _CACHE.pop(url,None);_SHOTS.pop(url,None)
            raise
        with _LOCK:shot=_SHOTS.get(url,'')
        if not shot:
            # A missing pageshot is transient state, so do not let the HTML
            # cache prevent another caller from retrying later in this run.
            with _LOCK:
                _CACHE.pop(url,None);_SHOTS.pop(url,None)
            raise GatewayError('Reader returned HTML without the requested full-page image')
    p=urlsplit(shot)
    if p.scheme!='https' or p.hostname!='storage.googleapis.com' or not p.path.startswith('/reader-6b7dc.appspot.com/ephemeral/'):
        raise GatewayError('Reader did not return a verified full-page image')
    try:
        body=_download_snapshot(shot)
        from PIL import Image
        picture=Image.open(io.BytesIO(body));picture.load()
        width,height=picture.size
        if not 320<=width<=2560 or height<100 or height>55040:raise GatewayError('Reader full-page image is outside the readable size limit')
        images=[];total=0
        for top in range(0,height,1720):
            stream=io.BytesIO();picture.crop((0,top,width,min(top+1800,height))).save(stream,format='PNG')
            body=stream.getvalue();data='data:image/png;base64,'+base64.b64encode(body).decode();total+=len(data)
            if len(images)>=32 or total>20*1024*1024:raise GatewayError('Reader full-page image cannot fit the complete vision input')
            images.append({'dataUrl':data,'hash':hashlib.sha256(body).hexdigest(),'pageSnapshot':True,'highDetail':True})
        return images
    except (OSError,ValueError) as exc:raise GatewayError('Reader full-page image could not be decoded') from None
