"""Use the existing Mindlogic key to extract text from official PDF attachments."""
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import requests
from ai_translate import DEFAULT_ENDPOINT
from crawl import BOARDS

API_PATH='/exa/contents'
class GatewayError(RuntimeError):
    """A public-loggable error that never contains request headers or keys."""

_CACHE={}
_LOCK=threading.Lock()

def clear_cache():
    with _LOCK:_CACHE.clear()

def _dotenv_value(name: str) -> str | None:
    """Read one requested value from .env without exposing the file contents."""
    path = Path(__file__).with_name(".env")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    prefix = name + "="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix):].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value or None
    return None


def _setting(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _dotenv_value(name) or default


def _endpoint() -> str:
    value = _setting("TRANSLATE_API_ENDPOINT", DEFAULT_ENDPOINT)
    parsed = urlsplit(value or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GatewayError("Configured gateway endpoint is not a valid HTTPS URL")
    return (value or "").rstrip("/") + API_PATH


def _validate_pdf_url(url):
    try:
        p=urlsplit(url);q=parse_qs(p.query)
        board=any((p.hostname,p.path)==(urlsplit(v[1]).hostname,urlsplit(v[1]).path) for v in BOARDS.values())
        good=board and p.scheme=='https' and not p.username and not p.password and p.port in (None,443)
        good=good and len(q.get('mode',[]))==1 and q['mode'][0] in ('download','file-download')
        good=good and len(q.get('articleNo',[]))==1 and q['articleNo'][0].isdigit()
        good=good and len(q.get('attachNo',[]))==1 and q['attachNo'][0].isdigit()
    except (TypeError,ValueError):good=False
    if not good:raise GatewayError('PDF URL is outside the official attachment allowlist')

def _fetch_pdf(url):
    _validate_pdf_url(url)
    key=_setting('TRANSLATE_API_KEY')
    if not key:raise GatewayError('TRANSLATE_API_KEY is not configured')
    endpoint=_endpoint()
    payload={'urls':[url],'text':{'includeHtmlTags':True},'maxAgeHours':0,'livecrawlTimeout':30000}
    for attempt in range(3):
        try:
            r=requests.post(endpoint,headers={'Authorization':'Bearer '+key},json=payload,timeout=(10,60),allow_redirects=False)
        except requests.RequestException as exc:
            if attempt<2:time.sleep(2**attempt);continue
            raise GatewayError('PDF gateway network error: '+type(exc).__name__) from None
        if r.status_code in (429,500,502,503,504) and attempt<2:time.sleep(2**attempt);continue
        if r.status_code!=200:raise GatewayError('PDF gateway HTTP '+str(r.status_code))
        try:body=r.json()
        except ValueError:raise GatewayError('PDF gateway returned invalid JSON') from None
        if not isinstance(body,dict) or not isinstance(body.get('statuses'),list) or not isinstance(body.get('results'),list):raise GatewayError('PDF gateway returned an invalid response shape')
        statuses=[s for s in body['statuses'] if isinstance(s,dict) and s.get('id')==url]
        pages=[p for p in body['results'] if isinstance(p,dict) and p.get('url')==url]
        if len(statuses)!=1 or statuses[0].get('status')!='success' or statuses[0].get('source')!='crawled':raise GatewayError('PDF gateway did not confirm a successful live crawl')
        if len(pages)!=1 or not isinstance(pages[0].get('text'),str) or not pages[0]['text'].strip():raise GatewayError('PDF gateway returned no readable attachment text')
        return {'url':url,'html':pages[0]['text'],'status':'success','source':'crawled'}
    raise GatewayError('PDF gateway retries exhausted')

def fetch_page(url):
    with _LOCK:cached=_CACHE.get(url)
    if cached is None:
        try:cached=_fetch_pdf(url)
        except GatewayError as exc:cached=exc
        with _LOCK:_CACHE[url]=cached
    if isinstance(cached,GatewayError):raise cached
    return cached
