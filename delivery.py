"""Post-deployment verification, optional push delivery and independent heartbeat."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
import requests

ROOT=Path(__file__).parent
SITE='https://zhupoxixixi.github.io/ajou-notices/'

def fingerprint(item):
    fields={k:item.get(k) for k in ('title','summary','audience','start','end','event','eventEnd','kind','eligibility','reviewNeeded')}
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def changes(data,state):
    if not state.get('initialized'):return []
    return [r for r in data['items'] if not r.get('reviewNeeded') and state.get('items',{}).get(r['id'])!=fingerprint(r)]

def notify(data,state,*,topic=None,client=None):
    client=client or requests
    rows=changes(data,state)
    if topic and rows:
        parts=[('新增：' if r['id'] not in state.get('items',{}) else '内容 / 日期更新：')+r['title'] for r in rows[:6]]
        if len(rows)>6:parts.append(f'另有 {len(rows)-6} 条，请打开公告站查看。')
        # Topic and credentials are passed in the request only, never persisted or logged.
        response=client.post('https://ntfy.sh/',json={'topic':topic,'title':f'亚洲大学公告 · {len(rows)} 条更新','message':'\n'.join(parts),'click':SITE},timeout=20)
        response.raise_for_status()
    result={'initialized':True,'items':{**state.get('items',{}),**{r['id']:fingerprint(r) for r in data['items']}}}
    return result,len(rows) if topic else 0

def verify(data,*,client=None):
    client=client or requests
    marker=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:16]
    for attempt in range(6):
        try:
            response=client.get(SITE+'notices.json?verify='+marker,timeout=15,headers={'Cache-Control':'no-cache'})
            response.raise_for_status()
            if response.json()==data:return
        except (requests.RequestException,ValueError):pass
        if attempt<5:time.sleep(4)
    raise RuntimeError('Published data does not match the built archive')

def healthy(data):
    return bool(data.get('sources')) and not data.get('errors') and not data.get('pending') and all(s.get('status')=='ok' for s in data.get('sources',[]))

def heartbeat(url,success,*,client=None):
    if not url:return
    if not url.startswith('https://'):raise ValueError('Heartbeat URL must use HTTPS')
    client=client or requests
    response=client.post(url.rstrip('/')+('' if success else '/fail'),data='Published data verified' if success else 'Notice refresh or publication needs attention',timeout=15)
    response.raise_for_status()

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['publish','failure']);args=p.parse_args()
    monitor=os.environ.get('HEALTHCHECK_PING_URL','') if os.environ.get('ENABLE_HEALTHCHECKS')=='true' else ''
    if args.action=='failure':
        heartbeat(monitor,False);print('Failure heartbeat '+('sent' if monitor else 'not configured'));return
    data=json.loads((ROOT/'dist/notices.json').read_text(encoding='utf8'))
    try:verify(data)
    except Exception:
        heartbeat(monitor,False);raise
    heartbeat(monitor,healthy(data))
    topic=os.environ.get('NTFY_TOPIC','') if os.environ.get('ENABLE_NOTIFICATIONS')=='true' else ''
    if topic:
        path=ROOT/'data/delivery.json'
        state=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        new,sent=notify(data,state,topic=topic)
        path.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('Notification baseline initialized' if not state.get('initialized') else f'Notified {sent} changes')
    else:print('Phone notifications not configured')
    print('Published archive verified; source health: '+('complete' if healthy(data) else 'partial'))
    if not healthy(data):raise RuntimeError('Published with partial source checks; retained archive remains available')

if __name__=='__main__':main()
