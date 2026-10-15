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
  const api={asTime,status,matches,sortItems,registrationClosed};root.NoticeCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
