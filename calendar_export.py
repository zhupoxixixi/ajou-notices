"""RFC 5545 calendar output for dated notices. No invented notification times."""
import datetime as dt
import re

KST=dt.timezone(dt.timedelta(hours=9))
SITE='https://zhupoxixixi.github.io/ajou-notices/'

def escape(value):
    return str(value or '').replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,').replace('\r','')

def fold(line):
    parts=[];part='';size=0
    for char in line:
        n=len(char.encode('utf8'))
        if size+n>73:
            parts.append(part);part=' ';size=1
        part+=char;size+=n
    parts.append(part)
    return '\r\n'.join(parts)

def stamp(value, fallback):
    try:
        parsed=dt.datetime.fromisoformat(value or fallback)
        if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=KST)
        return parsed.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    except (ValueError,TypeError):return '20261015T000000Z'

def temporal(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?',str(value)):return None
    try:return dt.datetime.fromisoformat(value).replace(tzinfo=KST)
    except ValueError:return None

def events_for(item, reviewed_at):
    if item.get('reviewNeeded') or item.get('eligibility')=='uncertain' or item.get('kind')=='guide':return []
    human=item.get('editorial')=='human'
    result=[]
    for kind,value,evidence in [('deadline',item.get('end'),item.get('endEvidence')),('event',item.get('event'),item.get('eventEvidence'))]:
        if not temporal(value) or (not human and not evidence):continue
        if kind=='deadline' and item.get('kind')=='event' and not item.get('eventEvidence'):continue
        end=item.get('eventEnd') if kind=='event' else None
        if kind=='event' and not end and item.get('kind')=='event' and not item.get('eventEvidence'):
            end=item.get('end') if (item.get('end') or '')>=value else None
        title=('申请 / 办理截止：' if kind=='deadline' else '活动：')+item['title']
        modified=stamp(item.get('translatedAt') or reviewed_at,reviewed_at)
        lines=['BEGIN:VEVENT','UID:'+escape(item['id']+'-'+kind+'@ajou-notices.zhupoxixixi.github.io'),'DTSTAMP:'+modified,'LAST-MODIFIED:'+modified]
        if 'T' in value:
            lines.append('DTSTART:'+stamp(value,reviewed_at))
            if end and temporal(end):
                if 'T' not in end:end+='T23:59'
                if temporal(end)>temporal(value):lines.append('DTEND:'+stamp(end,reviewed_at))
        else:
            lines.append('DTSTART;VALUE=DATE:'+value.replace('-',''))
            finish=(temporal(end) or temporal(value)).date()+dt.timedelta(days=1)
            lines.append('DTEND;VALUE=DATE:'+finish.strftime('%Y%m%d'))
        note='适用对象：'+item.get('audience','请查原文')+'\n'+item.get('summary','')+'\n'+('AI 自动整理，重要日期请核对原文。' if not human else '中文要点，办理前请核对最新原文。')+'\n官方原文：'+item['url']
        if 'T' not in value:note+='\n原文未给具体时刻，本日历使用全天事项。'
        lines.extend(['SUMMARY:'+escape(title),'DESCRIPTION:'+escape(note),'URL:'+SITE+'#notice-'+item['id'],'TRANSP:TRANSPARENT','END:VEVENT'])
        result.append(lines)
    return result

def calendar(events):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Ajou Notices CN//Academic notices//ZH-CN','CALSCALE:GREGORIAN','X-WR-CALNAME:亚洲大学中文公告','X-WR-TIMEZONE:Asia/Seoul']
    for event in events:lines.extend(event)
    return '\r\n'.join(fold(line) for line in lines+['END:VCALENDAR'])+'\r\n'
