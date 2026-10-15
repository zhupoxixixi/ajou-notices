'use strict';
(() => {
const $=s=>document.querySelector(s),data=window.AJOU_NOTICES,C=window.NoticeCore;
if(!data||!C){$('#updated').textContent='公告数据加载失败，请刷新页面。';return;}
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=u=>{try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?escape(x.href):'#';}catch{return '#';}};
const link=(u,label)=>`<a href="${safeUrl(u)}" target="_blank" rel="noopener noreferrer">${escape(label)} ↗</a>`;
const read=(k,f)=>{try{return JSON.parse(localStorage.getItem(k))??f;}catch{return f;}};
let saved=read('ajouNoticeSaved',[]);if(!Array.isArray(saved))saved=[];
let filters={tag:'',topic:'',source:'',status:'',q:'',saved:false},mode='priority',limit=12,view='all',currentId=null,lastFocus=null;
const labels={active:'时间范围内',upcoming:'即将开始',ended:'已截止 / 结束',guide:'常用指南',review:'更新待复核',unknown:'时间待确认'};
const date=v=>v?v.replace('T',' '):'未注明';
function timeLabel(r){if(r.kind==='guide')return '常规参考 · 详见适用条件';if(r.kind==='event')return '活动 '+date(r.event)+(r.end&&r.end.slice(0,10)!==r.event?.slice(0,10)?' — '+date(r.end):'');return '截止 '+date(r.end)+(r.end&&!r.end.includes('T')?' · 未注明时刻':'');}
function badge(r){const s=C.status(r);return `<span class="status-tag ${s}">${labels[s]}</span>`;}
function toast(t){$('#toast').textContent=t;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,2300);}
function persistSaved(){try{localStorage.setItem('ajouNoticeSaved',JSON.stringify(saved));}catch{toast('当前浏览器无法保存收藏，本次打开期间仍可使用。');}}
function toggleSaved(id){const added=!saved.includes(id);saved=added?[...saved,id]:saved.filter(x=>x!==id);persistSaved();render();if(currentId===id)$('#detailSave').textContent=added?'★ 已收藏':'☆ 收藏';toast(added?'已收藏到当前浏览器':'已取消收藏');}
function render(){
 const now=Date.now();const filtered=data.items.filter(r=>C.matches(r,filters,saved,now)&&(!filters.topic||r.tags.includes(filters.topic)));
 const rows=C.sortItems(filtered,mode,now);const shown=rows.slice(0,limit);
 $('#count').textContent=`${rows.length} 条`;$('#listTitle').textContent=filters.saved?'我的收藏':'公告收录';
 $('#list').innerHTML=shown.map(r=>`<article class="menu-card notice-card"><div class="card-header"><div class="card-topline"><span class="card-source">${escape(r.source)}${r.editorial==='auto'?' · AI 自动':''}</span>${badge(r)}<button class="save-button" data-save="${r.id}" aria-label="${saved.includes(r.id)?'取消收藏':'收藏'}：${escape(r.title)}" aria-pressed="${saved.includes(r.id)}">${saved.includes(r.id)?'★':'☆'}</button></div><h3><button data-detail="${r.id}" class="notice-title">${escape(r.title)}</button></h3><p class="dish-original">${escape(r.titleKo)}</p></div><div class="notice-content"><p class="summary">${escape(r.summary)}</p><p class="audience"><span>适用</span>${escape(r.audience)}</p><div class="tag-row">${r.tags.map(t=>`<span>${escape(t)}</span>`).join('')}</div></div><div class="card-footer"><span class="time-label">${escape(timeLabel(r))}</span><button class="small-button" data-detail="${r.id}">查看详情 <span aria-hidden="true">↗</span></button></div></article>`).join('')||`<div class="empty-state menu-card"><div class="empty-glyph">${filters.saved?'☆':'⌕'}</div><h3>${filters.saved?'还没有符合条件的收藏':'没有符合条件的公告'}</h3><p>${filters.saved?'点击公告右上角的星标即可收藏。':'试试缩短关键词，或重置筛选条件。'}</p><button class="small-button" data-reset>重置筛选</button></div>`;
 $('#loadMore').hidden=rows.length<=limit;$('#loadMore').textContent=`再显示 ${Math.min(12,rows.length-limit)} 条（共 ${rows.length} 条）`;
 $('#savedLabel').textContent=`收藏${saved.length?' · '+saved.length:''}`;
 document.querySelectorAll('#audienceTabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tag===filters.tag)));
 document.querySelectorAll('#topicTabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.topic===filters.topic)));
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
 $('#status').value=filters.status;$('#source').value=filters.source;
 $('#active').textContent=data.items.filter(r=>C.status(r,now)==='active').length;
}
function reset(){filters={tag:'',topic:'',source:'',status:'',q:'',saved:false};view='all';mode='priority';limit=12;$('#search').value='';$('#sort').value=mode;render();}
function openDetail(id,updateHash=true){
 const r=data.items.find(x=>x.id===id);if(!r)return;currentId=id;lastFocus=document.activeElement;
 $('#detailBody').innerHTML=`<div class="dialog-content"><div class="detail-meta">${badge(r)}<span>${escape(r.source)} · ${escape(r.published)}</span></div><h2 id="detailTitle" tabindex="-1">${escape(r.title)}</h2><p class="original-title">${escape(r.titleKo)}</p><div class="detail-facts"><p><b>适用对象</b>${escape(r.audience)}</p><p><b>办理 / 活动时间</b>${escape(timeLabel(r))}</p>${r.start?`<p><b>开始时间</b>${escape(date(r.start))}</p>`:''}${r.event&&r.kind!=='event'?`<p><b>活动日期</b>${escape(date(r.event))}</p>`:''}</div><h3>中文要点</h3><p>${escape(r.summary)}</p><ul>${r.details.map(t=>`<li>${escape(t)}</li>`).join('')}</ul>${r.note?`<aside class="editor-note"><b>适用提醒 / 整理说明</b><p>${escape(r.note)}</p></aside>`:''}${r.reviewNeeded?'<aside class="status-banner">原文在上次中文核验后发生变动，以下摘要需要复核，请优先查看官方原文。</aside>':''}<h3>原文与附件</h3><div class="detail-links">${link(r.url,'打开官方公告')}${r.extra.map(x=>link(x.url,x.label)).join('')}${r.attachments.map(x=>link(x.url,x.label)).join('')}</div><p class="verification">${r.editorial==='auto'?'AI 自动整理：'+escape((r.translatedAt||'').slice(0,10)):'人工核验：'+escape(data.reviewedAt)} · 最近原文检查：${escape((r.lastCheckedAt||r.fetchedAt||'').slice(0,10))} · 依据：${escape(r.evidence)}。附件提供官方下载链接，中文要点不是逐字全文翻译。</p><div class="detail-actions"><button id="detailSave" class="small-button">${saved.includes(id)?'★ 已收藏':'☆ 收藏'}</button><button id="copyLink" class="small-button">复制本条链接</button></div></div>`;
 if(!$('#detail').open)$('#detail').showModal();$('#detail').scrollTop=0;$('#detailTitle').focus();
 $('#detailSave').onclick=()=>toggleSaved(id);
 $('#copyLink').onclick=async()=>{try{await navigator.clipboard.writeText(location.href.split('#')[0]+'#notice-'+id);toast('已复制公告链接');}catch{toast('无法自动复制，请复制浏览器地址栏链接。');}};
 if(updateHash)history.replaceState(null,'','#notice-'+id);
}
function closeDetail(){if($('#detail').open)$('#detail').close();}
$('#detail').addEventListener('close',()=>{currentId=null;history.replaceState(null,'',location.pathname+location.search);if(lastFocus?.isConnected)lastFocus.focus();});
$('#closeDetail').onclick=closeDetail;$('#closeAbout').onclick=()=>$('#aboutDialog').close();
for(const el of [$('#detail'),$('#aboutDialog')])el.addEventListener('click',e=>{if(e.target===el){const r=el.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)el.close();}});
$('#list').onclick=e=>{const detail=e.target.closest('[data-detail]'),save=e.target.closest('[data-save]');if(detail)openDetail(detail.dataset.detail);else if(save)toggleSaved(save.dataset.save);else if(e.target.closest('[data-reset]'))reset();};
$('#audienceTabs').onclick=e=>{const b=e.target.closest('[data-tag]');if(b){filters.tag=b.dataset.tag;limit=12;render();}};
$('#topicTabs').innerHTML=['','课程学务','论文科研','奖学资助','生活签证','招生学位','就业活动'].map(t=>`<button class="window-button" data-topic="${t}" aria-pressed="${!t}">${t||'全部主题'}</button>`).join('');
$('#topicTabs').onclick=e=>{const b=e.target.closest('[data-topic]');if(b){filters.topic=b.dataset.topic;limit=12;render();}};
$('#search').oninput=e=>{filters.q=e.target.value;limit=12;render();};
$('#status').onchange=e=>{filters.status=e.target.value;limit=12;render();};$('#source').onchange=e=>{filters.source=e.target.value;limit=12;render();};$('#sort').onchange=e=>{mode=e.target.value;render();};$('#reset').onclick=reset;
$('#loadMore').onclick=()=>{limit+=12;render();};
function quick(value){reset();view=value==='all'?'all':value==='saved'?'saved':'active';filters.saved=value==='saved';filters.status=['active','guide'].includes(value)?value:'';render();window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>quick(b.dataset.view));document.querySelectorAll('[data-quick]').forEach(b=>b.onclick=()=>quick(b.dataset.quick));
$('#theme').onclick=()=>{const dark=document.documentElement.classList.toggle('dark');try{localStorage.setItem('ajouNoticeTheme',dark?'dark':'light');}catch{}$('#theme').setAttribute('aria-label',dark?'切换到浅色':'切换到深色');};
$('#about').onclick=()=>$('#aboutDialog').showModal();
$('#aboutBody').innerHTML=`<p>持续检查 <b>${data.sources.length} 个官方公告板各前 3 页</b>，并复查已收录公告。本次扫描 ${data.scanned} 条记录，已收录 ${data.items.length} 条中文摘要。</p><p>覆盖外国留学生、一般大学院、硕博学务及科研相关内容。并非全站历史公告全集，不包含登录后的课程平台通知。</p><p><b>自动更新：${escape(data.schedule||'每日 08:17、12:17、18:17 KST')}</b>。GitHub 定时执行可能延迟，最近一次检查见页面上方。</p><p>新增或内容变化的公告由 GPT-6 Luna 整理，标记“AI 自动”；首版人工核验内容保留原核验日期。AI 自动整理尚未逐条人工复核，申请资格和临时延期请对照原文。</p><h3>首版筛查时未纳入的项目</h3><ul>${data.exclusions.filter(x=>!data.items.some(r=>r.id===x.id)).map(x=>`<li>${link(x.url,x.title)}<p>${escape(x.reason)}</p></li>`).join('')}</ul><p>正文、海报或翻译获取失败时保留之前的条目，并显示待复核或更新异常。本次有 ${data.updateStats?.skipped||0} 条原文因失效图片等原因无法读取，未猜测内容。状态按韩国时间计算，“时间范围内”不保证尚有名额。</p><p>收藏只保存在当前浏览器，不跨设备同步。</p><p>${link('https://github.com/zhupoxixixi/ajou-notices','GitHub 仓库与运行记录')} · <a href="notices.json" download>下载 JSON</a> · <a href="THIRD_PARTY_NOTICES.md">界面许可</a></p>`;
$('#sourceLinks').innerHTML=data.sources.map(s=>link(s.url,s.name)).join('');$('#source').insertAdjacentHTML('beforeend',data.sources.map(s=>`<option value="${s.key}">${escape(s.name)}</option>`).join(''));
$('#total').textContent=data.items.length;$('#guides').textContent=data.items.filter(r=>r.kind==='guide').length;$('#updated').textContent=`最近检查 ${(data.checkedAt||data.fetchedAt).slice(0,10)} · ${data.sources.length} 个官方来源`;
$('#bottomMeta').textContent=`${data.items.length} 条中文公告 · 自动更新 ${data.translationModel||'gpt-6-luna'}`;
function checkAge(){
 const checked=Date.parse(data.checkedAt||data.fetchedAt);
 if(Date.now()-checked>3*86400000){$('#stale').hidden=false;$('#stale').textContent='公告已超过 3 天未成功更新，请查看官方原文。';}
 else if(data.errors?.length){$('#stale').hidden=false;$('#stale').textContent=`本次有 ${data.errors.length} 项更新未完成，已保留旧内容。请以对应官方原文为准。`;}
 else $('#stale').hidden=true;
}
checkAge();render();const initial=location.hash.match(/^#notice-(\d+)$/);if(initial)openDetail(initial[1],false);
window.addEventListener('hashchange',()=>{const m=location.hash.match(/^#notice-(\d+)$/);if(m)openDetail(m[1],false);});
setInterval(()=>{checkAge();render();},60000);
})();
