"""Public library API and graduate calendar; never access personal library messages."""
import datetime as dt
import hashlib
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

LIBRARY='https://library.ajou.ac.kr/pyxis-api/1/bulletin-boards/1/bulletins'
CALENDAR='https://grad.ajou.ac.kr/gs/bachelor/schedule.do'

def library_record(row):
    ident=str(row['id'])
    return {'id':'library-'+ident,'nativeId':ident,'board':'library','source':'中央图书馆','titleKo':row['title'],'published':row['dateCreated'][:10],
            'pinned':False,'url':'https://library.ajou.ac.kr/guide/bulletins/notice/'+ident}

def library_article(row):
    body=BeautifulSoup(row.get('content') or '','html.parser')
    return {'body':body.get_text('\n',strip=True),'images':[{'url':urljoin('https://library.ajou.ac.kr/',i['src']),'alt':i.get('alt','')} for i in body.select('img[src]')],
            'attachments':[{'url':a['href'],'label':a.get_text(' ',strip=True)} for a in body.select('a[href]') if a['href'].startswith('https://')],
            'published':row['dateCreated'][:10]}

def calendar_rows(html):
    soup=BeautifulSoup(html,'html.parser')
    heading=soup.select_one('h4')
    year_match=re.search(r'(20\d{2})학년도',soup.get_text(' ',strip=True))
    if not year_match:raise ValueError('Calendar academic year absent')
    year=int(year_match[1]);result=[]
    semester=1;counts={}
    for tr in soup.select('.ajou-gs-table tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.select('td')]
        if len(cells)<3:continue
        if len(cells)>3 and '2학기' in cells[0]:semester=2
        title,period,note=cells[-3:]
        if not title or not period:continue
        dates=[];current_year=year
        for m in re.finditer(r'(?:(20\d{2})\s*[.년]\s*)?(\d{1,2})\s*[.월]\s*(\d{1,2})\s*[.일]',period):
            if m[1]:current_year=int(m[1])
            elif semester==2 and int(m[2])<=2:current_year=year+1
            try:dates.append(dt.date(current_year,int(m[2]),int(m[3])).isoformat())
            except ValueError:pass
        stable=f'{year}|{semester}|{title}'
        occurrence=counts.get(stable,0);counts[stable]=occurrence+1
        ident='calendar-'+hashlib.sha256(f'{stable}|{occurrence}'.encode()).hexdigest()[:12]
        result.append({'id':ident,'board':'academic_calendar','source':'大学院学事日历','titleKo':title,'published':'','url':CALENDAR,'pinned':True,
                       'body':f'{year}학년도 대학원 학사일정\n{title}\n일정: {period}\n{note}\n세부 사항은 관련 공지사항 및 학과 안내 확인.','images':[],'attachments':[],
                       'calendarStart':dates[0] if dates else None,'calendarEnd':dates[-1] if dates else None,'calendarPeriod':period})
    if not result:raise ValueError('Calendar table empty')
    return result

def scan_special(board,known,today,fetcher):
    name='中央图书馆' if board=='library' else '大学院学事日历'
    url='https://library.ajou.ac.kr/guide/bulletins/notice' if board=='library' else CALENDAR
    health={'key':board,'name':name,'url':url,'pages':0,'scanned':0,'status':'ok','bounded':False}
    records=[]
    try:
        if board=='academic_calendar':
            records=calendar_rows(fetcher(CALENDAR));health['pages']=1
            records=[r for r in records if not r['calendarEnd'] or r['calendarEnd']>=(today-dt.timedelta(days=30)).isoformat()]
            health['boundary']='academic-year'
        else:
            for page in range(6):
                payload=json.loads(fetcher(LIBRARY+f'?offset={page*20}&max=20&onlyWriter=false&onlyNoticableBulletin=false&includeContent=true'))
                if not payload.get('success'):raise ValueError('Library response unsuccessful')
                raw=payload['data']['list'];health['pages']+=1
                rows=[library_record(r) for r in raw if not r.get('isPrivate') and not r.get('isPersonal')]
                records.extend(rows)
                if not raw or len(raw)<20:health['boundary']='last-page';break
                if rows and all(r['published']<(today-dt.timedelta(days=150)).isoformat() for r in rows):health['boundary']='date-window';break
                if page>=1 and all(r['id'] in known for r in rows):health['boundary']='known-page';break
            else:health.update(bounded=True,boundary='request-limit')
    except Exception as e:health.update(status='error',error=type(e).__name__)
    health['scanned']=len(records)
    return records,health
