(function(root){
  'use strict';
  function asTime(value,end=false){
    if(!value)return null;
    const suffix=value.includes('T')?(/(?:Z|[+-]\d{2}:\d{2})$/.test(value)?'':'+09:00'):(end?'T23:59:59.999+09:00':'T00:00:00+09:00');
    const result=Date.parse(value+suffix);return Number.isFinite(result)?result:null;
  }
  function status(item,now=Date.now()){
    if(item.reviewNeeded)return 'review';
    if(item.kind==='guide')return 'guide';
    if(item.event){
      const legacyEnd=item.kind==='event'&&!item.eventEvidence&&item.end&&item.end>=item.event?item.end:null;
      const finish=asTime(item.eventEnd||legacyEnd||item.event.slice(0,10),true),begin=asTime(item.event);
      if(finish!==null&&now>finish)return 'ended';
      if(begin!==null&&now<begin)return 'upcoming';
      return finish!==null?'active':'unknown';
    }
    const end=asTime(item.end,true),start=asTime(item.start);
    if(end!==null&&now>end)return 'ended';
    if(start!==null&&now<start)return 'upcoming';
    return end!==null?'active':'unknown';
  }
  function registrationClosed(item,now=Date.now()){
    return !!(item.event&&item.end&&(item.kind!=='event'||item.eventEvidence)&&asTime(item.end,true)!==null&&now>asTime(item.end,true)&&status(item,now)!=='ended');
  }
  function matches(item,filters,saved,now=Date.now()){
    const state=status(item,now);
    const sources=[item.board,...(item.otherSources||[]).map(x=>x.key)];
    return (!filters.tag||item.tags.includes(filters.tag))&&(!filters.source||sources.includes(filters.source))&&
      (filters.status==='current'?state!=='ended':!filters.status||state===filters.status)&&(!filters.saved||saved.includes(item.id))&&
      (!filters.q||[item.title,item.titleKo,item.summary,item.audience,...item.details,...item.tags].join(' ').toLowerCase().includes(filters.q.toLowerCase().trim()));
  }
  function sortItems(items,mode,now=Date.now()){
    const rank={active:0,upcoming:1,guide:2,review:3,unknown:4,ended:5};
    return [...items].sort((a,b)=>{
      if(mode==='latest')return (b.published||'').localeCompare(a.published||'')||b.id.localeCompare(a.id);
      const r=rank[status(a,now)]-rank[status(b,now)];if(r)return r;
      if(['active','upcoming'].includes(status(a,now)))return (asTime(a.event||a.end,true)||Infinity)-(asTime(b.event||b.end,true)||Infinity);
      return (b.published||'').localeCompare(a.published||'')||b.id.localeCompare(a.id);
    });
  }
  // Reject incomplete snapshots before replacing the usable in-memory archive.
  function validArchive(data){
    if(!data||!Array.isArray(data.items)||!data.items.length||!Array.isArray(data.sources)||!data.sources.length||!Array.isArray(data.exclusions))return false;
    if(!data.exclusions.every(x=>x&&typeof x.id==='string'&&typeof x.title==='string'&&typeof x.url==='string'&&typeof x.reason==='string'))return false;
    const checkedAt=data.checkedAt||data.fetchedAt;
    if(typeof checkedAt!=='string'||!Number.isFinite(Date.parse(checkedAt)))return false;
    if(data.referenceLinks!==undefined&&(!Array.isArray(data.referenceLinks)||data.referenceLinks.some(x=>!x||typeof x.name!=='string'||typeof x.url!=='string')))return false;
    const ids=new Set();
    return data.sources.every(s=>s&&['key','name','url'].every(k=>typeof s[k]==='string')&&/^[a-zA-Z0-9_-]+$/.test(s.key)&&
      ['checkedAt','lastSuccessAt','status'].every(k=>s[k]===undefined||s[k]===null||typeof s[k]==='string'))&&data.items.every(r=>{
      if(!r||typeof r.id!=='string'||!/^[a-zA-Z0-9-]+$/.test(r.id)||ids.has(r.id))return false;
      ids.add(r.id);
      return ['title','titleKo','summary','audience','source','board'].every(k=>typeof r[k]==='string')&&
        ['tags','details'].every(k=>Array.isArray(r[k])&&r[k].every(x=>typeof x==='string'))&&
        ['extra','attachments'].every(k=>Array.isArray(r[k])&&r[k].every(x=>x&&typeof x.url==='string'&&typeof x.label==='string'))&&
        ['published','kind','url','start','end','event','eventEnd','eventEvidence','calendarFile','note','evidence','fetchedAt','lastCheckedAt','translatedAt','eligibility','editorial','fetchStatus']
          .every(k=>r[k]===undefined||r[k]===null||typeof r[k]==='string')&&
        (r.otherSources===undefined||Array.isArray(r.otherSources)&&r.otherSources.every(x=>x&&typeof x.key==='string'&&typeof x.name==='string'&&typeof x.url==='string'));
    });
  }
  const api={asTime,status,matches,sortItems,registrationClosed,validArchive};root.NoticeCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
