"""Build offline-capable GitHub Pages assets from persistent Chinese summaries."""
import json, shutil
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
    data['items']=list(records.values())
    assert data['items'] and len({x['id'] for x in data['items']})==len(data['items'])
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    for name in ('index.html','styles.css','notice.css','app.js','core.js','favicon.svg','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/'src'/name,dist/name)
    serialized=json.dumps(data,ensure_ascii=False,indent=2)
    (dist/'notices.json').write_text(serialized+'\n',encoding='utf8')
    (dist/'data.js').write_text('window.AJOU_NOTICES = '+serialized+';\n',encoding='utf8')
    (dist/'.nojekyll').write_text('',encoding='utf8')
    lines=['# 亚洲大学中文公告',f"最近检查：{data.get('checkedAt',data['fetchedAt'])}（韩国时间）。中文为要点整理，AI自动整理不等于人工核验。",'']
    for r in data['items']:
        lines.extend([f"## {r['title']}",f"原题：{r['titleKo']}",f"来源：{r['source']} | 发布：{r['published']}",f"适用：{r['audience']}",r['summary'],*['- '+s for s in r['details']],f"补充：{r['note']}" if r.get('note') else '',f"[官方原文]({r['url']})",''])
    (dist/'亚洲大学中文公告.md').write_text('\n\n'.join(lines),encoding='utf8')
    print('Built',len(data['items']),'notices')
if __name__=='__main__':build()
