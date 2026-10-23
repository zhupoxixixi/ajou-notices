"""Build offline-capable GitHub Pages assets from persistent Chinese summaries."""
import json, shutil, hashlib, datetime as dt
from calendar_export import calendar, events_for
from crawl import BOARDS
from pathlib import Path
ROOT=Path(__file__).parent

def build():
    path=ROOT/'data/archive.json'
    if not path.exists():path=ROOT/'data/seed.json'
    data=json.loads(path.read_text(encoding='utf8'))
    # Confirmed bilingual versions of the same official notices share one card.
    aliases={'377144':'377134','377183':'376934','375652':'375650','375648':'375643','377427':'377426','376257':'376256','375923':'375924','374887':'374886','375155':'375153','377439':'377425','373219':'373075'}
    records={x['id']:x for x in data['items']}
    for other,primary in aliases.items():
        if other in records and primary in records:
            item=records[primary];alt=records.pop(other)
            item['extra']=[x for x in item.get('extra',[]) if x['url']!=alt['url']]+[{'label':'同一通知的英文版本','url':alt['url']}]
            shared=item.get('otherSources',[])+alt.get('otherSources',[])+[{'key':alt['board'],'name':alt['source'],'url':alt['url']}]
            item['otherSources']=list({x['url']:x for x in shared if x['url']!=item['url']}.values())
    data['items']=list(records.values())
    old_sources={s['key']:s for s in data.get('sources',[])}
    data['sources']=[{'key':key,'name':name,'url':url,**old_sources.get(key,{})} for key,(name,url) in BOARDS.items()]
    data['referenceLinks']=[{'name':'网络安全学科官网','url':'https://security.ajou.ac.kr/'},{'name':'学院研究生综合考试要求','url':'https://www.ajou.ac.kr/sw/grad/comprehensive-examination.do'}]
    assert data['items'] and len({x['id'] for x in data['items']})==len(data['items'])
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    assets=('index.html','styles.css','notice.css','app.js','core.js','appearance.js','background.js','contrast.js','favicon.svg','THIRD_PARTY_NOTICES.md','manifest.webmanifest','404.html')
    for name in assets:
        shutil.copy2(ROOT/'src'/name,dist/name)
    if (ROOT/'src/icons').exists():shutil.copytree(ROOT/'src/icons',dist/'icons',dirs_exist_ok=True)
    if (ROOT/'src/assets').exists():shutil.copytree(ROOT/'src/assets',dist/'assets',dirs_exist_ok=True)
    caldir=dist/'calendar';caldir.mkdir(exist_ok=True)
    for stale in caldir.glob('*.ics'):stale.unlink()
    all_events=[]
    history_path=ROOT/'data/calendar_state.json'
    previous=json.loads(history_path.read_text(encoding='utf8')) if history_path.exists() else {}
    history={}
    for item in data['items']:
        events=events_for(item,data.get('reviewedAt') or '2026-10-15')
        if events:
            for event in events:
                uid=next(line[4:] for line in event if line.startswith('UID:'))
                old=previous.get(uid,{})
                fields=[line for line in event if not line.startswith(('DTSTAMP:','LAST-MODIFIED:','SEQUENCE:'))]
                changed=old.get('fields')!=fields or old.get('cancelled',False)
                sequence=old.get('sequence',0)+(1 if old and changed else 0)
                event.insert(-1,'SEQUENCE:'+str(sequence))
                history[uid]={'fields':fields,'sequence':sequence,'event':event,'cancelled':False}
            all_events.extend(events);item['calendarFile']='calendar/'+item['id']+'.ics'
            (caldir/(item['id']+'.ics')).write_bytes(calendar(events).encode('utf8'))
        else:item.pop('calendarFile',None)
    for uid,old in previous.items():
        if uid in history:continue
        event=[line for line in old['event'] if not line.startswith(('STATUS:','SEQUENCE:'))]
        if not old.get('cancelled'):
            modified=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            event=[line.split(':',1)[0]+':'+modified if line.startswith(('DTSTAMP:','LAST-MODIFIED:')) else line for line in event]
        sequence=old.get('sequence',0)+(0 if old.get('cancelled') else 1)
        event[-1:-1]=['STATUS:CANCELLED','SEQUENCE:'+str(sequence)]
        history[uid]={**old,'sequence':sequence,'event':event,'cancelled':True}
        all_events.append(event)
    history_path.write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (dist/'notices.ics').write_bytes(calendar(all_events).encode('utf8'))
    digest=hashlib.sha256()
    def asset_digest(path):
        # Git normalizes text line endings; cache versions must agree on Windows and CI.
        return path.read_bytes() if path.suffix.lower() in ('.png','.jpg','.jpeg','.webp') else path.read_text(encoding='utf8').encode('utf8')
    for name in assets:
        digest.update(asset_digest(dist/name))
    for folder in ('assets','icons'):
        for asset in sorted((dist/folder).rglob('*')) if (dist/folder).exists() else []:
            if asset.is_file():digest.update(asset_digest(asset))
    digest.update(asset_digest(ROOT/'src/sw.js'))
    version=digest.hexdigest()[:12]
    (dist/'sw.js').write_text((ROOT/'src/sw.js').read_text(encoding='utf8').replace('__VERSION__',version),encoding='utf8')
    serialized=json.dumps(data,ensure_ascii=False,indent=2)
    (dist/'notices.json').write_text(serialized+'\n',encoding='utf8')
    (dist/'data.js').write_text('window.AJOU_NOTICES = '+serialized+';\n',encoding='utf8')
    (dist/'.nojekyll').write_text('',encoding='utf8')
    lines=['# 亚洲大学中文公告',f"最近检查：{data.get('checkedAt',data['fetchedAt'])}（韩国时间）。中文为要点整理，AI自动整理不等于人工核验。",'']
    for r in data['items']:
        lines.extend([f"## {r['title']}",f"原题：{r['titleKo']}",f"来源：{r['source']} | 发布：{r['published']}",f"适用：{r['audience']}",r['summary'],*['- '+s for s in r['details']],f"补充：{r['note']}" if r.get('note') else '',f"[官方原文]({r['url']})",''])
    (dist/'亚洲大学中文公告.md').write_text('\n\n'.join(lines).rstrip()+'\n',encoding='utf8')
    print('Built',len(data['items']),'notices')
if __name__=='__main__':build()
