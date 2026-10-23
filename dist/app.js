'use strict';
(async () => {
const $=s=>document.querySelector(s),C=window.NoticeCore;
let data=window.AJOU_NOTICES;
if(!data||!C){$('#updated').textContent='公告数据加载失败，请刷新页面。';return;}
// An installed browser may reuse its old bootstrap script while offline.
// Prefer the validated snapshot saved by the last successful manual refresh.
if(!navigator.onLine&&'caches' in window){
 try{
  for(const key of (await caches.keys()).filter(k=>k.startsWith('ajou-notices-')).reverse()){
   const response=await (await caches.open(key)).match(new URL('notices.json',location.href).href);
   if(!response)continue;
   const snapshot=await response.json();
   if(C.validArchive(snapshot)){data=snapshot;window.AJOU_NOTICES=snapshot;break;}
  }
 }catch{/* Keep the bundled archive if offline storage is unavailable. */}
}
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=u=>{try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?escape(x.href):'#';}catch{return '#';}};
const link=(u,label)=>`<a href="${safeUrl(u)}" target="_blank" rel="noopener noreferrer">${escape(label)} ↗</a>`;
const read=(k,f)=>{try{return JSON.parse(localStorage.getItem(k))??f;}catch{return f;}};
let saved=read('ajouNoticeSaved',[]);if(!Array.isArray(saved))saved=[];
let filters={tag:'',topic:'',source:'',status:'current',q:'',saved:false},mode='priority',limit=12,view='current',currentId=null,lastFocus=null;
const labels={active:'时间范围内',upcoming:'即将开始',ended:'已截止 / 结束',guide:'常用指南',review:'更新待复核',unknown:'时间待确认'};
const date=v=>v?v.replace('T',' '):'未注明';
function timeLabel(r){if(r.kind==='guide')return '常规参考 · 详见适用条件';if(r.event){const legacy=r.kind==='event'&&!r.eventEvidence&&r.end&&r.end>=r.event;return '活动 '+date(r.event)+(legacy?' — '+date(r.end):r.end?' · '+(C.registrationClosed(r)?'报名已截止':'报名截止 '+date(r.end)):'');}return r.end?'截止 '+date(r.end)+(!r.end.includes('T')?' · 未注明时刻':''):'期限待确认 · 请查原文';}
function badge(r){const s=C.status(r);return `<span class="status-tag ${s}">${labels[s]}</span>${r.eligibility==='uncertain'?'<span class="status-tag review">资格需确认</span>':''}${r.fetchStatus==='stale'?'<span class="status-tag review">原文检查失败</span>':''}`;}
function toast(t){$('#toast').textContent=t;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,2300);}
function persistSaved(){try{localStorage.setItem('ajouNoticeSaved',JSON.stringify(saved));}catch{toast('当前浏览器无法保存收藏，本次打开期间仍可使用。');}}
function toggleSaved(id){const added=!saved.includes(id);saved=added?[...saved,id]:saved.filter(x=>x!==id);persistSaved();render();if(currentId===id)$('#detailSave').textContent=added?'★ 已收藏':'☆ 收藏';toast(added?'已收藏到当前浏览器':'已取消收藏');}
function render(){
 const now=Date.now();const filtered=data.items.filter(r=>C.matches(r,filters,saved,now)&&(!filters.topic||r.tags.includes(filters.topic)));
 const rows=C.sortItems(filtered,mode,now);const shown=rows.slice(0,limit);
 $('#count').textContent=`${rows.length} 条`;$('#listTitle').textContent=filters.saved?'我的收藏':'公告收录';
 const ended=data.items.filter(r=>C.status(r,now)==='ended').length;
 $('#archiveHint').innerHTML=filters.status==='current'?`已隐藏 ${ended} 条已结束事项，常用指南和期限待确认项目仍保留。<button class="text-button" id="showArchive">查看全部</button>`:filters.saved?'收藏包含已结束公告，链接持续保留。':'';
 if($('#showArchive'))$('#showArchive').onclick=()=>{filters.status='';limit=12;render();};
 $('#list').innerHTML=shown.map(r=>`<article class="menu-card notice-card glass-surface"><div class="glass-content"><div class="card-header"><div class="card-topline"><span class="card-source">${escape(r.source)}${r.editorial==='auto'?' · AI 自动':''}</span>${badge(r)}<button class="save-button" data-save="${r.id}" aria-label="${saved.includes(r.id)?'取消收藏':'收藏'}：${escape(r.title)}" aria-pressed="${saved.includes(r.id)}">${saved.includes(r.id)?'★':'☆'}</button></div><h3><button data-detail="${r.id}" class="notice-title">${escape(r.title)}</button></h3></div><div class="notice-content"><p class="summary">${escape(r.summary)}</p><p class="audience"><span>适用</span>${escape(r.audience)}</p><div class="tag-row">${r.tags.map(t=>`<span>${escape(t)}</span>`).join('')}</div></div><div class="card-footer"><span class="time-label">${escape(timeLabel(r))}</span><button class="small-button" data-detail="${r.id}">查看详情 <span aria-hidden="true">↗</span></button></div></div></article>`).join('')||`<div class="empty-state menu-card"><div class="empty-glyph">${filters.saved?'☆':'⌕'}</div><h3>${filters.saved?'还没有符合条件的收藏':'没有符合条件的公告'}</h3><p>${filters.saved?'点击公告右上角的星标即可收藏。':'试试缩短关键词，或重置筛选条件。'}</p><button class="small-button" data-reset>重置筛选</button></div>`;
 $('#loadMore').hidden=rows.length<=limit;$('#loadMore').textContent=`再显示 ${Math.min(12,rows.length-limit)} 条（共 ${rows.length} 条）`;
 $('#savedLabel').textContent=`收藏${saved.length?' · '+saved.length:''}`;
 document.querySelectorAll('#audienceTabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tag===filters.tag)));
 document.querySelectorAll('#topicTabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.topic===filters.topic)));
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
 $('#status').value=filters.status;$('#source').value=filters.source;
 $('#active').textContent=data.items.filter(r=>C.status(r,now)==='active').length;
}
function reset(){filters={tag:'',topic:'',source:'',status:'current',q:'',saved:false};view='current';mode='priority';limit=12;$('#search').value='';$('#sort').value=mode;render();}
function openDetail(id,updateHash=true){
 const r=data.items.find(x=>x.id===id);if(!r)return;currentId=id;lastFocus=document.activeElement;
 $('#detailBody').innerHTML=`<div class="dialog-content"><div class="detail-meta">${badge(r)}<span>${escape(r.source)} · ${escape(r.published)}</span></div><h2 id="detailTitle" tabindex="-1">${escape(r.title)}</h2><details class="original-heading"><summary>查看原文标题</summary><p class="original-title" lang="ko">${escape(r.titleKo)}</p></details><div class="detail-facts"><p><b>适用对象</b>${escape(r.audience)}</p><p><b>办理 / 活动时间</b>${escape(timeLabel(r))}</p>${r.start?`<p><b>开始时间</b>${escape(date(r.start))}</p>`:''}${r.event&&r.kind!=='event'?`<p><b>活动日期</b>${escape(date(r.event))}</p>`:''}</div><h3>中文要点</h3><p>${escape(r.summary)}</p><ul>${r.details.map(t=>`<li>${escape(t)}</li>`).join('')}</ul>${r.note?`<aside class="editor-note"><b>适用提醒 / 整理说明</b><p>${escape(r.note)}</p></aside>`:''}${r.reviewNeeded?'<aside class="status-banner">原文在上次中文核验后发生变动，以下摘要需要复核，请优先查看官方原文。</aside>':''}<h3>原文与附件</h3><div class="detail-links">${link(r.url,'打开官方公告')}${r.extra.map(x=>link(x.url,x.label)).join('')}${r.attachments.map(x=>link(x.url,x.label)).join('')}</div><p class="verification">${r.editorial==='auto'?'AI 自动整理：'+escape((r.translatedAt||'').slice(0,10)):'人工核验：'+escape(data.reviewedAt)} · 最近原文检查：${escape((r.lastCheckedAt||r.fetchedAt||'').slice(0,10))} · 依据：${escape(r.evidence)}。附件提供官方下载链接，中文要点不是逐字全文翻译。</p><div class="detail-actions"><button id="detailSave" class="small-button">${saved.includes(id)?'★ 已收藏':'☆ 收藏'}</button><button id="copyLink" class="small-button">复制本条链接</button></div></div>`;
 if(!$('#detail').open)$('#detail').showModal();$('#detail').scrollTop=0;$('#detailTitle').focus();
 $('#detailSave').onclick=()=>toggleSaved(id);
 if(r.calendarFile){const a=document.createElement('a');a.className='small-button';a.href=r.calendarFile;a.download='ajou-'+id+'.ics';a.textContent='加入日历';$('#detailBody .detail-actions').append(a);}
 if(r.otherSources?.length){const p=document.createElement('p');p.innerHTML='同时发布于：'+r.otherSources.map(s=>link(s.url,s.name)).join(' · ');$('#detailBody .detail-links').append(p);}
 $('#copyLink').onclick=async()=>{try{await navigator.clipboard.writeText(location.href.split('#')[0]+'#notice-'+id);toast('已复制公告链接');}catch{toast('无法自动复制，请复制浏览器地址栏链接。');}};
 if(updateHash)history.replaceState(null,'','#notice-'+id);
}
function closeDetail(){if($('#detail').open)$('#detail').close();}
$('#detail').addEventListener('close',()=>{currentId=null;history.replaceState(null,'',location.pathname+location.search);if(lastFocus?.isConnected)lastFocus.focus();});
$('#closeDetail').onclick=closeDetail;$('#closeAbout').onclick=()=>$('#aboutDialog').close();$('#closeTools').onclick=()=>$('#toolsDialog').close();
for(const el of [$('#detail'),$('#aboutDialog'),$('#toolsDialog')])el.addEventListener('click',e=>{if(e.target===el){const r=el.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)el.close();}});
$('#list').onclick=e=>{const detail=e.target.closest('[data-detail]'),save=e.target.closest('[data-save]');if(detail)openDetail(detail.dataset.detail);else if(save)toggleSaved(save.dataset.save);else if(e.target.closest('[data-reset]'))reset();};
$('#audienceTabs').onclick=e=>{const b=e.target.closest('[data-tag]');if(b){filters.tag=b.dataset.tag;limit=12;render();}};
$('#topicTabs').innerHTML=['','课程学务','论文科研','奖学资助','生活签证','招生学位','就业活动'].map(t=>`<button class="window-button" data-topic="${t}" aria-pressed="${!t}">${t||'全部主题'}</button>`).join('');
$('#topicTabs').onclick=e=>{const b=e.target.closest('[data-topic]');if(b){filters.topic=b.dataset.topic;limit=12;render();}};
$('#search').oninput=e=>{filters.q=e.target.value;limit=12;render();};
$('#status').onchange=e=>{filters.status=e.target.value;limit=12;render();};$('#source').onchange=e=>{filters.source=e.target.value;limit=12;render();};$('#sort').onchange=e=>{mode=e.target.value;render();};$('#reset').onclick=reset;
$('#loadMore').onclick=()=>{limit+=12;render();};
function quick(value){reset();view=['current','saved','active'].includes(value)?value:'current';filters.saved=value==='saved';filters.status=['current','active','guide'].includes(value)?value:'';render();window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>quick(b.dataset.view));document.querySelectorAll('[data-quick]').forEach(b=>b.onclick=()=>{quick(b.dataset.quick);$('#toolsDialog').close();});
function themeLabel(){const dark=document.documentElement.classList.contains('dark');$('#theme').setAttribute('aria-pressed',String(dark));$('#theme').textContent=dark?'切换浅色':'切换深色';}
$('#theme').onclick=()=>{const dark=document.documentElement.classList.toggle('dark');try{localStorage.setItem('ajouNoticeTheme',dark?'dark':'light');}catch{}themeLabel();};themeLabel();
$('#about').onclick=()=>$('#aboutDialog').showModal();
$('#toolsToggle').onclick=()=>$('#toolsDialog').showModal();
$('#tools').onclick=()=>{const open=$('#calendarTools').hidden;$('#calendarTools').hidden=!open;$('#tools').setAttribute('aria-expanded',String(open));};
$('#copyCalendar').onclick=async()=>{try{await navigator.clipboard.writeText(new URL('notices.ics',location.href).href.split('#')[0]);toast('已复制日历订阅地址');}catch{toast('订阅地址：'+new URL('notices.ics',location.href).href);}};
function metadata(){
$('#aboutBody').innerHTML=`<p>持续检查 <b>${data.sources.length} 个官方来源</b>，按近期日期、已知记录或请求上限翻页，并复查已收录公告。本次扫描 ${data.scanned} 条记录，收录 ${data.items.length} 条摘要。各来源的结果见设置中的来源状态。</p><p>覆盖外国留学生、一般大学院、硕博学务及科研相关内容。并非全站历史公告全集，不包含登录后的课程平台通知。</p><p><b>自动更新：${escape(data.schedule||'每日 08:17、12:17、18:17 KST')}</b>。GitHub 定时执行可能延迟，最近一次检查见列表底部。</p><p>新增或内容变化的公告由 GPT-6 Luna 整理，标记“AI 自动”；首版人工核验内容保留原核验日期。AI 自动整理尚未逐条人工复核，申请资格和临时延期请对照原文。</p><h3>首版筛查时未纳入的项目</h3><ul>${data.exclusions.filter(x=>!data.items.some(r=>r.id===x.id)).map(x=>`<li>${link(x.url,x.title)}<p>${escape(x.reason)}</p></li>`).join('')}</ul><p>正文、海报或翻译获取失败时保留之前的条目，并显示待复核或更新异常。本次有 ${data.updateStats?.skipped||0} 条原文因失效图片等原因无法读取，未猜测内容。状态按韩国时间计算，“时间范围内”不保证尚有名额。</p><p>收藏只保存在当前浏览器，不跨设备同步。</p><p>${link('https://github.com/zhupoxixixi/ajou-notices','GitHub 仓库与运行记录')} · <a href="notices.json" download>下载 JSON</a> · <a href="THIRD_PARTY_NOTICES.md">界面许可</a></p>`;
$('#sourceLinks').innerHTML=data.sources.map(s=>link(s.url,s.name)).join('');$('#source').innerHTML='<option value="">全部官方来源</option>'+data.sources.map(s=>`<option value="${s.key}">${escape(s.name)}</option>`).join('');
const healthLabels={ok:'本次检查完成',partial:'部分公告待处理',error:'本次读取失败'};
$('#sourceHealth').innerHTML=data.sources.map(s=>`<div class="health-row"><div><b>${escape(s.name)}</b><span>${healthLabels[s.status]||'等待首次检查'}${s.bounded?' · 已达本次扫描上限':''}</span></div><small>${s.checkedAt?'检查 '+escape(s.checkedAt.slice(0,16).replace('T',' ')):'尚无检查记录'}${s.lastSuccessAt?'<br>最近成功检查 '+escape(s.lastSuccessAt.slice(0,16).replace('T',' ')):''}${s.pages?' · '+s.pages+' 页':''}</small></div>`).join('');
$('#coverageNote').textContent=`本次扫描 ${data.scanned} 条、${data.pages} 页。按近期日期、已知记录或页数上限停止，并非完整历史档案。${data.pending?.length||0} 条内容仍待处理；登录后的课程和个人通知未接入。`;
$('#total').textContent=data.items.length;$('#guides').textContent=data.items.filter(r=>r.kind==='guide').length;$('#updated').textContent=`最近检查 ${(data.checkedAt||data.fetchedAt).slice(0,16).replace('T',' ')} KST · ${data.sources.length} 个来源`;
$('#bottomMeta').textContent=`${data.items.length} 条中文公告 · 日期均为韩国时间`;
departmentNote();
}
function checkAge(){
 const checked=Date.parse(data.checkedAt||data.fetchedAt);
 if(Date.now()-checked>86400000){$('#stale').hidden=false;$('#stale').textContent='公告已超过 24 小时未成功检查，请查看官方原文。';}
 else if(data.errors?.length||data.pending?.length){$('#stale').hidden=false;$('#stale').textContent=`本次有 ${Math.max(data.errors?.length||0,data.pending?.length||0)} 项更新未完成，已保留旧内容。请以对应官方原文为准。`;}
 else $('#stale').hidden=true;
}
function departmentNote(){
$('#aboutBody').insertAdjacentHTML('beforeend',`<h3>网络安全学科</h3><p>사이버보안학과 官网的“大学院公告”指向已接入的一般大学院主板；软件融合学院的混合公告另行筛选。其他专业的专属要求不能直接用于本学科。</p><p>${(data.referenceLinks||[]).map(s=>link(s.url,s.name)).join(' · ')}</p>`);
}
function offlineState(){$('#offline').hidden=navigator.onLine;$('#offline').textContent=`当前离线，显示缓存公告（检查于 ${(data.checkedAt||data.fetchedAt).slice(0,16).replace('T',' ')} KST）。联网后刷新以查看最新资料。`;}
window.addEventListener('offline',offlineState);window.addEventListener('online',()=>{offlineState();toast('网络已恢复，可刷新获取最新公告');});offlineState();
let installPrompt;window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;$('#installApp').hidden=false;});$('#installApp').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('#installApp').hidden=true;}};
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js',{scope:'./',updateViaCache:'none'}).catch(()=>{});
metadata();checkAge();render();const initial=location.hash.match(/^#notice-([a-zA-Z0-9-]+)$/);if(initial)openDetail(initial[1],false);
window.addEventListener('hashchange',()=>{const m=location.hash.match(/^#notice-([a-zA-Z0-9-]+)$/);if(m)openDetail(m[1],false);});

let refreshing=false;
$('#refreshButton').onclick=async()=>{
 if(refreshing)return;
 const status=$('#refreshStatus');status.hidden=false;
 if(!navigator.onLine){status.textContent='当前离线，保留已缓存公告。联网后再试。';return;}
 refreshing=true;$('#refreshButton').disabled=true;$('#refreshButton').setAttribute('aria-busy','true');status.textContent='正在检查已发布公告…';
 const previousData=data;
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
 try{
  const response=await fetch('notices.json?refresh='+Date.now(),{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('HTTP '+response.status);
  const next=await response.json();
  if(!C.validArchive(next))throw Error('Invalid archive');
  const changed=JSON.stringify(next)!==JSON.stringify(data);
  data=next;window.AJOU_NOTICES=next;metadata();checkAge();render();updateClock();offlineState();
  if(currentId&&$('#detail').open)openDetail(currentId,false);
  status.textContent=changed?'已载入最新公告，筛选和收藏已保留。':'当前已是最新公告。';
  if('serviceWorker' in navigator)navigator.serviceWorker.getRegistration().then(r=>r?.update()).catch(()=>{});
 }catch{
  if(data!==previousData){
   data=previousData;window.AJOU_NOTICES=previousData;
   try{metadata();checkAge();render();offlineState();if(currentId&&$('#detail').open)openDetail(currentId,false);}catch{}
  }
  status.textContent='刷新未完成，已保留当前公告和筛选。请稍后重试。';
 }
 finally{clearTimeout(timeout);refreshing=false;$('#refreshButton').disabled=false;$('#refreshButton').removeAttribute('aria-busy');}
};

let lastStates='';
function updateClock(){checkAge();const states=data.items.map(r=>r.id+':'+C.status(r)).join('|');if(states!==lastStates){lastStates=states;render();}}
updateClock();setInterval(updateClock,60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateClock();});
})();
