"""Bounded official-board crawl. No credentials; originals retained for review."""
import argparse, datetime as dt, hashlib, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
BOARDS = {
    'graduate': ('一般大学院', 'https://grad.ajou.ac.kr/gs/community/notice.do'),
    'international': ('外国人留学生', 'https://www.ajou.ac.kr/iadmissions/life/lifenotice.do'),
    'oia': ('国际交流处', 'https://www.ajou.ac.kr/oia/notice/notice.do'),
    'university': ('学校综合公告', 'https://www.ajou.ac.kr/kr/ajou/notice.do'),
    'graduate_en': ('大学院英文公告', 'https://grad.ajou.ac.kr/gs_eng/community/notice.do'),
}

def fetch(url):
    r = requests.get(url, timeout=35, headers={'User-Agent': 'AjouNoticeArchive/1.0 (public academic notice reader)'})
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
        found[ident] = {'id': ident, 'board': board, 'source': BOARDS[board][0], 'titleKo': title, 'published': date, 'pinned': 'b-top-box' in row.get('class', []), 'url': base + '?mode=view&articleNo=' + ident}
    return list(found.values())

def article(html, url):
    s = BeautifulSoup(html, 'html.parser')
    body = s.select_one('.b-content-box') or s.select_one('.b-content') or s.select_one('.view-content')
    if body is None:
        raise ValueError('Article body selector not found')
    for el in body.select('script,style'):
        el.decompose()
    published = s.select_one('meta[property="article:published_time"]')
    return {
        **({'published': published['content'][:10]} if published else {}),
        'body': body.get_text('\n', strip=True),
        'links': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url,a['href'])} for a in body.select('a[href]') if a['href'].startswith(('http', '/', '?'))],
        'attachments': [{'label': a.get_text(' ', strip=True), 'url': urljoin(url,a['href'])} for a in s.select('a[href*="mode=download"]')],
        'images': [{'alt': i.get('alt', ''), 'url': urljoin(url, i['src'])} for i in body.select('img[src]')],
        'sha256': hashlib.sha256(html.encode()).hexdigest(),
    }

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
