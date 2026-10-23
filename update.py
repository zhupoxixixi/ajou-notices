"""Discover, recheck and translate notices; preserve previous results on failure."""
import base64, datetime as dt, hashlib, json, os, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
from crawl import BOARDS, listing, article, fetch, scan_board, session
from ai_translate import translate_notice, DEFAULT_MODEL
ROOT=Path(__file__).parent;KST=dt.timezone(dt.timedelta(hours=9));PROMPT_VERSION=2
def read(path,default):
    try:return json.loads(path.read_text(encoding='utf8'))
    except FileNotFoundError:return default
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(path)
def digest(data):return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def base_fingerprint(r):return digest({k:r.get(k) for k in ('titleKo','published','body','images','attachments')})
def allowed_url(url):
    p=urlparse(url);return p.scheme=='https' and (p.hostname in ('ajou.ac.kr','ksdcdb.kr') or (p.hostname or '').endswith('.ajou.ac.kr')) and not p.username

def binary_resource(url,limit):
    """Use the same bounded connection retries for posters/PDFs as for pages."""
    response=session().get(url,timeout=(8,30),headers={'User-Agent':'AjouNoticeArchive/1.0 (public academic notice reader)'})
    response.raise_for_status()
    if len(response.content)>limit:raise ValueError('Official resource exceeds size limit')
    return response
def protect_scope(item):
    if item and item['id']=='373075':
        text='该公告工时表为本科口径，不能直接推定适用于硕博；研究生应另向学校和出入境确认。'
        if text not in (item.get('note') or ''):item={**item,'note':(item.get('note') or '')+' '+text}
    return item
def candidate(r,known,today):
    if r['id'] in known:return True
    if not r.get('pinned') and r.get('published'):
        try:
            if (today-dt.date.fromisoformat(r['published'])).days>150:return False
        except ValueError:pass
    if re.search(r'\[학부\]|학부생\s*대상|대한민국\s*국적|한국\s*국적자',r['titleKo']) and not re.search(r'대학원|석사|박사',r['titleKo']):return False
    if r['board']=='university':return bool(re.search(r'외국인|유학생|대학원|석사|박사|BK21|연구|국제|International|인터내셔널|글로벌|논문|학술|세미나|특강|도서관|장학|취업|채용|주차|안전|등록|수료|인권|성희롱|폭력|글쓰기|인공지능',r['titleKo'],re.I))
    if r['board']=='oia':
        if re.search(r'학부.*연계',r['titleKo']):return False
        return bool(re.search(r'외국인|유학생|대학원|석사|박사|foreigner|international|global|A\.G\.A|festival|visa|한국어|장학|취업|채용',r['titleKo'],re.I))
    if r['board']=='library':return bool(re.search(r'학술|연구|논문|대학원|JCR|DB|데이터|Turnitin|학위|교육|전자자료|EndNote|JIF|ICPSR',r['titleKo'],re.I))
    return True
def image_evidence(images):
    result=[]
    for image in images[:4]:
        if image['url'].startswith('data:image/') and ';base64,' in image['url']:
            header,encoded=image['url'].split(',',1);mime=header[5:].split(';')[0];body=base64.b64decode(encoded,validate=True)
        else:
            if not allowed_url(image['url']):raise ValueError('Untrusted image host')
            r=binary_resource(image['url'],12*1024*1024);body=r.content;mime=r.headers.get('Content-Type','image/jpeg').split(';')[0]
        if len(body)>12*1024*1024:raise ValueError('Poster exceeds size limit')
        if not mime.startswith('image/'):raise ValueError('Poster is not an image')
        result.append({**image,'hash':hashlib.sha256(body).hexdigest(),'dataUrl':'data:'+mime+';base64,'+base64.b64encode(body).decode()})
    return result
def source_for(row,prior):
    if row['board']=='library':
        from public_sources import LIBRARY,library_article
        if row.get('body') or row.get('images'):
            # The public includeContent list is authoritative too. Some listed
            # notices reject the detail route even while publishing their body.
            source={**row,'extraText':''}
        else:
            payload=json.loads(fetch('https://library.ajou.ac.kr/pyxis-api/1/bulletins/'+row['id'].split('-',1)[1]+'?includeContent=true'))
            if not payload.get('success'):raise ValueError('Library detail failed')
            detail=payload['data']
            if detail.get('isPrivate') or detail.get('isPersonal'):raise ValueError('Non-public library notice')
            source={**row,**library_article(detail),'extraText':''}
        images=source['images'];source['images']=[i for i in images if allowed_url(i['url']) or i['url'].startswith('data:image/')]
        source['unreadableImages']=len(images)-len(source['images'])
        if not source['body'] and not source['images']:source['unavailableReason']='图书馆公告无可读取正文或有效海报，未猜测内容。'
        return source
    if row['board']=='academic_calendar':
        from public_sources import CALENDAR,calendar_rows
        if 'body' not in row:
            row=next((r for r in calendar_rows(fetch(CALENDAR)) if r['id']==row['id']),None)
            if row is None:raise ValueError('Calendar item removed')
        return {**row,'extraText':''}
    html=fetch(row['url']);source={**row,**article(html,row['url'])}
    title=BeautifulSoup(html,'html.parser').select_one('.b-title-box')
    if title:
        full=re.sub(r'^\[[^\]]+\]\s*','',title.get_text(' ',strip=True)).strip()
        old=re.sub(r'^(?:\[[^\]]+\]\s*)+','',(prior or row)['titleKo']).strip()
        source['titleKo']=(prior or row)['titleKo'] if full==old else full
    extra=[]
    for x in (prior or {}).get('extra',[]):
        if x['url']=='https://taekwondo.jbcomz.co.kr/':extra.append(BeautifulSoup(fetch(x['url']),'html.parser').get_text(' ',strip=True)[:18000])
    source['extraText']='\n'.join(extra)
    original_images=source['images']
    source['images']=[x for x in original_images if allowed_url(x['url']) or x['url'].startswith('data:image/')]
    source['unreadableImages']=len(original_images)-len(source['images'])
    if not source['body'] and not source['images']:
        pdf=next((a for a in source['attachments'] if a['label'].lower().endswith('.pdf')),None)
        if pdf and allowed_url(pdf['url']):
            import io
            from pypdf import PdfReader
            r=binary_resource(pdf['url'],10*1024*1024)
            reader=PdfReader(io.BytesIO(r.content));text='\n'.join(p.extract_text() or '' for p in reader.pages[:12])
            # Scanned manuals may expose page numbers but no actual prose.
            # Do not send those numbers to the model as if the PDF was read.
            if len(re.findall(r'[A-Za-z\u4e00-\u9fff\uac00-\ud7a3]',text))>=30:
                source['body']=text
                if len(reader.pages)>12:source['extraText']+='\nPDF仅提取前12页，未读取其余页面。'
            else:source['unavailableReason']='PDF为扫描件，未取得可核验正文，不能仅凭页码生成摘要。'
    if not source['body'] and not source['images']:source.setdefault('unavailableReason','官方页面无可读取正文、有效海报或可提取文本的PDF，未猜测内容。')
    return source

def needs_source_retry(state):
    return state.get('action')=='skipped' or any(x in state.get('reason','') for x in ('无可读取','无法读取','扫描件','未取得可核验'))
def process(row,prior,state,seed,model,now):
    minutes=int(os.environ.get('SOURCE_CACHE_MINUTES','0'))
    if state and state.get('model')==model and minutes>0 and (not prior or prior.get('fetchStatus')!='stale') and not needs_source_retry(state):
        age=dt.datetime.fromisoformat(now)-dt.datetime.fromisoformat(state['checkedAt'])
        if dt.timedelta(0)<=age<dt.timedelta(minutes=minutes):
            cached={**prior,'otherSources':row.get('otherSources',prior.get('otherSources',[]))} if prior else None
            return protect_scope(cached),state,'unchanged'
    source=source_for(row,prior);base=base_fingerprint(source);pictures=image_evidence(source.get('images',[]))
    key=digest({'base':base,'posters':[x['hash'] for x in pictures],'extra':source['extraText'],'model':model,'prompt':PROMPT_VERSION})
    record={k:source[k] for k in ('id','titleKo','url','source','board','published','attachments')};record['fetchedAt']=now
    record['otherSources']=row.get('otherSources',[])
    record['displayUntil']=row.get('displayUntil')
    new_state={'fingerprint':key,'checkedAt':now,'sourceFingerprint':base,'model':model}
    if source.get('unavailableReason'):
        old={**prior,'reviewNeeded':True,'fetchStatus':'stale'} if prior else None
        return old,{**new_state,'reason':source['unavailableReason'],'action':'skipped'},'skipped'
    if prior and prior.get('editorial')=='auto' and any(s in (prior.get('note') or '') for s in ('中国公民不符合','中国申请人不符合','仅限韩国国籍')):
        return None,{**new_state,'reason':prior['note']},'excluded'
    if not prior and state and state.get('sourceFingerprint')==base and state.get('reason') and not needs_source_retry(state):
        return None,{**new_state,'reason':state['reason']},'excluded'
    if state and state.get('fingerprint')==key:return (protect_scope({**prior,**record,'lastCheckedAt':now,'fetchStatus':'ok','reviewNeeded':False}) if prior else None),{**state,**new_state},'unchanged'
    if seed and seed.get('reviewedFingerprint')==base:return {**seed,**record,'lastCheckedAt':now,'editorial':'human','fetchStatus':'ok'},new_state,'unchanged'
    if not prior and not candidate(source,set(),dt.date.fromisoformat(now[:10])):
        new_state['reason']='正文日期不在近期收录范围';return None,new_state,'excluded'
    poster_count=len(source.get('images',[]))
    source['images']=pictures
    decision=translate_notice(source,model=model)
    if not decision['include']:
        new_state['reason']=decision['reason'];return None,new_state,'excluded'
    if row['board']=='academic_calendar':
        decision.update(start=source.get('calendarStart'),end=source.get('calendarEnd'),event=None,eventEnd=None,kind='deadline',endEvidence=source.get('calendarPeriod') if source.get('calendarEnd') else '')
        decision['note']=(decision.get('note') or '')+' 大学院通用学事日程，个人办理资格及学科细节以专项公告为准；日程可能调整。'
    item={**record,**{k:decision.get(k) for k in ('title','tags','audience','summary','details','start','end','event','eventEnd','kind','note','endEvidence','eventEvidence','eligibility')},'editorial':'auto','translationModel':model,'translatedAt':now,'lastCheckedAt':now,'fetchStatus':'ok','reviewNeeded':False,'evidence':'官方正文与海报，由 GPT-6 Luna 自动整理','extra':(prior or {}).get('extra',[])}
    if poster_count>4:item['note']=(item.get('note') or '')+' 海报仅识别前4张，请对照完整原文。'
    if source.get('unreadableImages'):item['note']=(item.get('note') or '')+' 官方页面含失效 blob 图片，以上内容仅依据可读取正文和附件。'
    return protect_scope(item),new_state,'translated'
def run():
    env=ROOT/'.env'
    if env.exists():
        for line in env.read_text(encoding='utf8').splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip().strip('\"\''))
    if not os.environ.get('TRANSLATE_API_KEY'):raise RuntimeError('TRANSLATE_API_KEY missing')
    seed=read(ROOT/'data/seed.json',{});archive=read(ROOT/'data/archive.json',seed)
    items={r['id']:r for r in archive['items']};seeds={r['id']:r for r in seed['items']};states=read(ROOT/'data/state.json',{})
    now=dt.datetime.now(KST).isoformat();today=dt.date.fromisoformat(now[:10]);model=os.environ.get('TRANSLATE_MODEL') or DEFAULT_MODEL
    rows={};errors=[];coverage=[];pending=[]
    previous_sources={s['key']:s for s in archive.get('sources',[])}
    for board,(_,url) in BOARDS.items():
        print(f'[listing] {board}',flush=True)
        result,health=scan_board(board,set(states)|set(items),today)
        health['checkedAt']=now
        health['lastSuccessAt']=previous_sources.get(board,{}).get('lastSuccessAt')
        coverage.append(health)
        if health['status']=='error':errors.append({'board':board,'error':health['error']})
        for row in result:
            if row['id'] in rows:
                rows[row['id']].setdefault('otherSources',[]).append({'key':board,'name':row['source'],'url':row['url']})
            else:rows[row['id']]=row
    if sum(x['status']=='ok' for x in coverage)<max(3,len(BOARDS)//2+1):raise RuntimeError('Most official boards failed; leaving published data unchanged')
    for ident,r in items.items():rows.setdefault(ident,{k:r[k] for k in ('id','board','source','titleKo','published','url')})
    hard_exclusions={r['id'] for r in seed.get('exclusions',[]) if '未展开' not in r['reason']}
    tasks=[r for r in rows.values() if r['id'] not in hard_exclusions and candidate(r,set(items),today)]
    stats={'checkedAt':now,'model':model,'scanned':len(rows),'pages':sum(x['pages'] for x in coverage),'boards':sum(x['status']=='ok' for x in coverage),'translated':0,'unchanged':0,'excluded':0,'skipped':0,'errors':errors,'schedule':'每日 08:17、12:17、18:17 KST','sourceStatus':coverage}
    failures=0
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(process,row,items.get(row['id']),states.get(row['id']),seeds.get(row['id']),model,now):row for row in tasks}
        for job in as_completed(jobs):
            row=jobs[job];ident=row['id']
            try:
                result,state,action=job.result();states[ident]=state;stats[action]+=1
                if action=='skipped':
                    pending.append({'id':ident,'board':row['board'],'url':row['url'],'reason':state.get('reason','原文不完整')})
                    for health in coverage:
                        if health['key']==row['board'] and health['status']=='ok':health['status']='partial'
                if result:items[ident]=result
                else:items.pop(ident,None)
                print(f'[{ident}] {action}',flush=True)
            except Exception as e:
                failures+=1;stats['errors'].append({'id':ident,'error':type(e).__name__})
                from ai_translate import TranslationError
                reason=str(e)[:300] if isinstance(e,TranslationError) else type(e).__name__
                stats['errors'][-1]['reason']=reason
                pending.append({'id':ident,'board':row['board'],'url':row['url'],'reason':reason})
                for health in coverage:
                    if health['key']==row['board'] and health['status']=='ok':health['status']='partial'
                if ident in items:
                    items[ident]={**items[ident],'fetchStatus':'stale','reviewNeeded':isinstance(e,TranslationError) or items[ident].get('reviewNeeded',False)}
                print(f'[{ident}] '+('retained previous data' if ident in items else 'not published')+f' ({reason})',flush=True)
    if not stats['translated'] and not stats['unchanged']:raise RuntimeError('No successful source checks; leaving published data unchanged')
    for health in coverage:
        if health['status']=='ok':health['lastSuccessAt']=now
    archive={**seed,'items':list(items.values()),'sources':coverage,'pending':pending,'scanned':len(rows),'pages':stats['pages'],'checkedAt':now,'updatedAt':now,'automatic':True,'schedule':stats['schedule'],'translationModel':model,'errors':stats['errors'],'updateStats':{k:v for k,v in stats.items() if k!='errors'}}
    write(ROOT/'data/archive.json',archive);write(ROOT/'data/state.json',states);write(ROOT/'data/update.json',stats)
    print(json.dumps({'items':len(items),**stats},ensure_ascii=False))
    if failures or errors:print('Partial update: failed items retained and marked for review.',flush=True)
    return archive
if __name__=='__main__':run()
