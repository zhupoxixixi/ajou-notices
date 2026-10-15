"""Discover, recheck and translate notices; preserve previous results on failure."""
import base64, datetime as dt, hashlib, json, os, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
from crawl import BOARDS, listing, article, fetch
from ai_translate import translate_notice, DEFAULT_MODEL
ROOT=Path(__file__).parent;KST=dt.timezone(dt.timedelta(hours=9));PROMPT_VERSION=1
def read(path,default):
    try:return json.loads(path.read_text(encoding='utf8'))
    except FileNotFoundError:return default
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(path)
def digest(data):return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def base_fingerprint(r):return digest({k:r.get(k) for k in ('titleKo','published','body','images','attachments')})
def allowed_url(url):
    p=urlparse(url);return p.scheme=='https' and (p.hostname=='ajou.ac.kr' or (p.hostname or '').endswith('.ajou.ac.kr')) and not p.username
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
    if r['board']=='university':return bool(re.search(r'외국인|유학생|대학원|석사|박사|BK21|연구|국제|International|인터내셔널|글로벌',r['titleKo'],re.I))
    if r['board']=='oia':
        if re.search(r'학부·석사|학부.*연계|파견.*교환',r['titleKo']):return False
        return bool(re.search(r'외국인|유학생|대학원|석사|박사|foreigner|international day|global ambassador|A\.G\.A|festival',r['titleKo'],re.I))
    return True
def image_evidence(images):
    result=[]
    for image in images[:4]:
        if image['url'].startswith('data:image/') and ';base64,' in image['url']:
            header,encoded=image['url'].split(',',1);mime=header[5:].split(';')[0];body=base64.b64decode(encoded,validate=True)
        else:
            if not allowed_url(image['url']):raise ValueError('Untrusted image host')
            r=requests.get(image['url'],timeout=30);r.raise_for_status();body=r.content;mime=r.headers.get('Content-Type','image/jpeg').split(';')[0]
        if len(body)>12*1024*1024:raise ValueError('Poster exceeds size limit')
        if not mime.startswith('image/'):raise ValueError('Poster is not an image')
        result.append({**image,'hash':hashlib.sha256(body).hexdigest(),'dataUrl':'data:'+mime+';base64,'+base64.b64encode(body).decode()})
    return result
def source_for(row,prior):
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
            r=requests.get(pdf['url'],timeout=30);r.raise_for_status()
            if len(r.content)>10*1024*1024:raise ValueError('PDF exceeds size limit')
            reader=PdfReader(io.BytesIO(r.content));source['body']='\n'.join(p.extract_text() or '' for p in reader.pages[:12])
    if not source['body'] and not source['images']:source['unavailableReason']='官方页面无可读取正文、有效海报或可提取文本的PDF，未猜测内容。'
    return source
def process(row,prior,state,seed,model,now):
    source=source_for(row,prior);base=base_fingerprint(source);pictures=image_evidence(source.get('images',[]))
    key=digest({'base':base,'posters':[x['hash'] for x in pictures],'extra':source['extraText'],'model':model,'prompt':PROMPT_VERSION})
    record={k:source[k] for k in ('id','titleKo','url','source','board','published','attachments')};record['fetchedAt']=now
    new_state={'fingerprint':key,'checkedAt':now,'sourceFingerprint':base,'model':model}
    if source.get('unavailableReason'):
        old={**prior,'reviewNeeded':True,'fetchStatus':'stale'} if prior else None
        return old,{**new_state,'reason':source['unavailableReason']},'skipped'
    if prior and prior.get('editorial')=='auto' and any(s in (prior.get('note') or '') for s in ('中国公民不符合','中国申请人不符合','仅限韩国国籍')):
        return None,{**new_state,'reason':prior['note']},'excluded'
    if state and state.get('fingerprint')==key:return (protect_scope({**prior,'fetchedAt':now,'lastCheckedAt':now,'fetchStatus':'ok','reviewNeeded':False}) if prior else None),{**state,**new_state},'unchanged'
    if not state and seed and seed.get('reviewedFingerprint')==base:return {**seed,**record,'lastCheckedAt':now,'editorial':'human','fetchStatus':'ok'},new_state,'unchanged'
    if not prior and not candidate(source,set(),dt.date.fromisoformat(now[:10])):
        new_state['reason']='正文日期不在近期收录范围';return None,new_state,'excluded'
    poster_count=len(source.get('images',[]))
    source['images']=pictures
    decision=translate_notice(source,model=model)
    if not decision['include']:
        new_state['reason']=decision['reason'];return None,new_state,'excluded'
    item={**record,**{k:decision.get(k) for k in ('title','tags','audience','summary','details','start','end','event','kind','note','endEvidence')},'editorial':'auto','translationModel':model,'translatedAt':now,'lastCheckedAt':now,'fetchStatus':'ok','reviewNeeded':False,'evidence':'官方正文与海报，由 GPT-6 Luna 自动整理','extra':(prior or {}).get('extra',[])}
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
    rows={};errors=[];coverage=[]
    for board,(_,url) in BOARDS.items():
        for page in range(3):
            try:
                result=listing(fetch(url+f'?mode=list&articleLimit=10&article.offset={10*page}'),url,board)
                if not result:raise ValueError('Empty official listing')
                coverage.append({'board':board,'page':page,'count':len(result)})
                for row in result:rows.setdefault(row['id'],row)
            except Exception as e:errors.append({'board':board,'page':page,'error':type(e).__name__})
            time.sleep(.2)
    if len({x['board'] for x in coverage})<3:raise RuntimeError('Most official boards failed; leaving published data unchanged')
    for ident,r in items.items():rows.setdefault(ident,{k:r[k] for k in ('id','board','source','titleKo','published','url')})
    hard_exclusions={r['id'] for r in seed.get('exclusions',[]) if '未展开' not in r['reason']}
    tasks=[r for r in rows.values() if r['id'] not in hard_exclusions and candidate(r,set(items),today)]
    stats={'checkedAt':now,'model':model,'scanned':len(rows),'pages':len(coverage),'boards':len({x['board'] for x in coverage}),'translated':0,'unchanged':0,'excluded':0,'skipped':0,'errors':errors,'schedule':'每日 08:17、12:17、18:17 KST'}
    failures=0
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(process,row,items.get(row['id']),states.get(row['id']),seeds.get(row['id']),model,now):row for row in tasks}
        for job in as_completed(jobs):
            row=jobs[job];ident=row['id']
            try:
                result,state,action=job.result();states[ident]=state;stats[action]+=1
                if result:items[ident]=result
                else:items.pop(ident,None)
                print(f'[{ident}] {action}',flush=True)
            except Exception as e:
                failures+=1;stats['errors'].append({'id':ident,'error':type(e).__name__})
                if ident in items:items[ident]={**items[ident],'fetchStatus':'stale','reviewNeeded':True}
                print(f'[{ident}] '+('retained previous data' if ident in items else 'not published')+f' ({type(e).__name__})',flush=True)
    if not stats['translated'] and not stats['unchanged']:raise RuntimeError('No successful source checks; leaving published data unchanged')
    archive={**seed,'items':list(items.values()),'scanned':len(rows),'pages':len(coverage),'checkedAt':now,'updatedAt':now,'automatic':True,'schedule':stats['schedule'],'translationModel':model,'errors':stats['errors'],'updateStats':{k:v for k,v in stats.items() if k!='errors'}}
    write(ROOT/'data/archive.json',archive);write(ROOT/'data/state.json',states);write(ROOT/'data/update.json',stats)
    print(json.dumps({'items':len(items),**stats},ensure_ascii=False))
    if failures or errors:print('Partial update: failed items retained and marked for review.',flush=True)
    return archive
if __name__=='__main__':run()
