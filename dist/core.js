(function(root){
  'use strict';
  const asTime=(value,end=false)=>value?Date.parse(value+(value.includes('T')?':00+09:00':(end?'T23:59:59.999+09:00':'T00:00:00+09:00'))):null;
  function status(item,now=Date.now()){
    if(item.reviewNeeded)return 'review';
    if(item.kind==='guide')return 'guide';
    const eventEnd=item.kind==='event'&&item.event?item.event.slice(0,10):null;
    const end=asTime(item.end||eventEnd,true),start=asTime(item.start|| (item.kind==='event'?item.event:null));
    if(end!==null&&now>end)return 'ended';
    if(start!==null&&now<start)return 'upcoming';
    return end!==null?'active':'unknown';
  }
  function matches(item,filters,saved,now=Date.now()){
    const state=status(item,now);
    return (!filters.tag||item.tags.includes(filters.tag))&&(!filters.source||item.board===filters.source)&&
      (!filters.status||state===filters.status)&&(!filters.saved||saved.includes(item.id))&&
      (!filters.q||[item.title,item.titleKo,item.summary,item.audience,...item.details,...item.tags].join(' ').toLowerCase().includes(filters.q.toLowerCase().trim()));
  }
  function sortItems(items,mode,now=Date.now()){
    const rank={active:0,upcoming:1,guide:2,review:3,unknown:4,ended:5};
    return [...items].sort((a,b)=>{
      if(mode==='latest')return b.published.localeCompare(a.published)||b.id.localeCompare(a.id);
      const r=rank[status(a,now)]-rank[status(b,now)];if(r)return r;
      if(['active','upcoming'].includes(status(a,now)))return (asTime(a.end,true)||Infinity)-(asTime(b.end,true)||Infinity);
      return b.published.localeCompare(a.published)||b.id.localeCompare(a.id);
    });
  }
  const api={asTime,status,matches,sortItems};root.NoticeCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
