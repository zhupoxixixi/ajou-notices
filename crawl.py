"""Bounded official-board crawl. No credentials; originals retained for review."""
import argparse, datetime as dt, hashlib, json, re, time, threading
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
BOARDS = {
    'graduate': ('一般大学院', 'https://grad.ajou.ac.kr/gs/community/notice.do'),
    'international': ('外国人留学生', 'https://www.ajou.ac.kr/iadmissions/life/lifenotice.do'),
    'oia': ('国际交流处', 'https://www.ajou.ac.kr/oia/notice/notice.do'),
    'university': ('学校综合公告', 'https://www.ajou.ac.kr/kr/ajou/notice.do'),
    'graduate_en': ('大学院英文公告', 'https://grad.ajou.ac.kr/gs_eng/community/notice.do'),
    'innovation': ('大学院创新 / BK21', 'https://grad.ajou.ac.kr/gs/bk21/bk21_bbs.do'),
    'scholarship': ('奖学金公告', 'https://www.ajou.ac.kr/kr/ajou/notice_scholarship.do'),
    'library': ('中央图书馆', 'https://library.ajou.ac.kr/guide/bulletins/notice'),
    'academic_calendar': ('大学院学事日历', 'https://grad.ajou.ac.kr/gs/bachelor/schedule.do'),
    'college': ('软件融合学院', 'https://www.ajou.ac.kr/sw/board/notice.do'),
}
BOARD_RULES = {}
_CLIENTS=threading.local()

def session():
    if not hasattr(_CLIENTS,'session'):
        client=requests.Session()
        client.mount('https://',HTTPAdapter(max_retries=Retry(total=2,connect=2,read=1,backoff_factor=.75,status_forcelist=(429,500,502,503,504),allowed_methods=('GET',))))
        _CLIENTS.session=client
    return _CLIENTS.session

def fetch(url):
    r = session().get(url, timeout=(8, 15), headers={'User-Agent': 'AjouNoticeArchive/1.0 (public academic notice reader)'})
    r.raise_for_status()
    r.encoding = 'utf-8'
    return r.text

def listing(html, base, board):
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    for a in soup.select('a[href*="articleNo="]'):
        url = urljoin(base, a['href'])
        q = parse_qs(urlparse(url).query)
        if q.get('mode', [''])[0] != 'view':
            continue
        ident = q['articleNo'][0]
        row = a.find_parent('tr') or a.find_parent('li') or a.parent
        title = a.get_text(' ', strip=True)
        if not title or title in ('첨부파일', '파일'):
            continue
        date_node = row.select_one('.b-date')
        date = date_node.get_text(strip=True).replace('.', '-') if date_node else ''
        if re.fullmatch(r'\d{2}-\d{2}-\d{2}', date):
            date = '20' + date
        display_until = '공지마감일' in soup.get_text(' ',strip=True) or BOARD_RULES.get(board,{}).get('date')=='displayUntil'
        found[ident] = {'id': ident, 'board': board, 'source': BOARDS[board][0], 'titleKo': title, 'published': '' if display_until else date, 'displayUntil': date if display_until else None, 'pinned': 'b-top-box' in row.get('class', []), 'url': base + '?mode=view&articleNo=' + ident}
    return list(found.values())

def article(html, url):
    s = BeautifulSoup(html, 'html.parser')
    body = s.select_one('.b-content-box') or s.select_one('.b-content') or s.select_one('.view-content')
    if body is None:
        raise ValueError('Article body selector not found')
    for el in body.select('script,style'):
        el.decompose()
    published = s.select_one('meta[property="article:published_time"]')
    date_box = s.select_one('.b-etc-box') or s.select_one('.b-view-info')
    date_match = re.search(r'(?<!\d)(20\d{2})[.\-/](\d{2})[.\-/](\d{2})(?!\d)',date_box.get_text(' ',strip=True)) if date_box else None
    return {
        **({'published': published['content'][:10]} if published else {'published':'-'.join(date_match.groups())} if date_match else {}),
        'body': body.get_text('\n', strip=True),
        'links': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url,a['href'])} for a in body.select('a[href]') if a['href'].startswith(('http', '/', '?'))],
        'attachments': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url,a['href'])} for a in s.select('a[href*="mode=download"]')],
        'images': [{'alt': i.get('alt', ''), 'url': urljoin(url, i['src'])} for i in body.select('img[src]')],
        'sha256': hashlib.sha256(html.encode()).hexdigest(),
    }

def scan_board(board, known, today, *, fetcher=None, max_pages=None):
    """Scan until an actual boundary; expose a cap instead of claiming full coverage."""
    fetcher = fetcher or fetch
    if board in ('library','academic_calendar'):
        from public_sources import scan_special
        return scan_special(board,known,today,fetcher)
    max_pages = max_pages or (10 if board=='university' else 8)
    name, base = BOARDS[board]
    records, seen, pages = {}, set(), 0
    state = {'key':board,'name':name,'url':base,'pages':0,'scanned':0,'status':'ok','bounded':False}
    for page in range(max_pages):
        try:
            rows = listing(fetcher(base+f'?mode=list&articleLimit=10&article.offset={10*page}'),base,board)
            if not rows: raise ValueError('Empty official listing')
            pages += 1
            fresh = [r for r in rows if r['id'] not in seen]
            if not fresh:
                state['boundary']='repeated-page'; break
            for row in fresh: records[row['id']]=row
            seen.update(r['id'] for r in rows)
            ordinary = [r for r in rows if not r['pinned']]
            dates = [r['published'] for r in ordinary if r.get('published')]
            cutoff = (today-dt.timedelta(days=150)).isoformat()
            if ordinary and len(dates)==len(ordinary) and all(d<cutoff for d in dates):
                state['boundary']='date-window'; break
            if page>=1 and ordinary and all(r['id'] in known for r in ordinary):
                state['boundary']='known-page'; break
            if len(ordinary)<10:
                state['boundary']='last-page'; break
        except Exception as e:
            state.update(status='error',error=type(e).__name__); break
    else:
        state.update(bounded=True,boundary='request-limit')
    state.update(pages=pages,scanned=len(records))
    return list(records.values()),state

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pages', type=int, default=3)
    p.add_argument('--details', action='store_true')
    args = p.parse_args()
    out = ROOT / 'research'
    (out / 'raw').mkdir(parents=True, exist_ok=True)
    records, errors, coverage = {}, [], []
    for board, (_, url) in BOARDS.items():
        for page in range(args.pages):
            target = url + f'?mode=list&articleLimit=10&article.offset={page*10}'
            try:
                html = fetch(target)
                (out / 'raw' / f'{board}-{page}.html').write_text(html, encoding='utf-8')
                rows = listing(html, url, board)
                coverage.append({'board':board,'url':target,'count':len(rows)})
                for row in rows:
                    records.setdefault(row['id'], row)
            except Exception as e:
                errors.append({'url':target,'error':str(e)})
            time.sleep(.25)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    if args.details:
        for row in records.values():
            try:
                html = fetch(row['url'])
                (out / 'raw' / f"{row['id']}.html").write_text(html, encoding='utf-8')
                row.update(article(html,row['url']))
                row['fetchedAt'] = now
            except Exception as e:
                errors.append({'url':row['url'],'error':str(e)})
            time.sleep(.25)
    result = {'fetchedAt': now, 'coverage':coverage,'errors':errors,'records':list(records.values())}
    (out / 'crawl.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'records':len(records),'errors':errors,'coverage':coverage},ensure_ascii=False))

if __name__ == '__main__':
    main()
