async (page) => {
 const checks=[],errors=[];const ok=(v,n)=>{if(!v)throw Error(n);checks.push(n);};
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8789/');
 await page.evaluate(()=>{localStorage.removeItem('ajouNoticeSaved');localStorage.setItem('ajouNoticeTheme','light');});await page.reload();
 const data=await page.evaluate(()=>window.AJOU_NOTICES),Cnow=await page.evaluate(()=>Date.now());
 const expected=await page.evaluate(()=>window.AJOU_NOTICES.items.filter(r=>window.NoticeCore.status(r)!=='ended').length);
 ok(await page.locator('#count').textContent()===expected+' 条','homepage hides ended notices');
 ok(!(await page.locator('#list .status-tag.ended').count()),'ended badges absent from homepage');
 await page.locator('#showArchive').click();ok(await page.locator('#count').textContent()===data.items.length+' 条','archive keeps all records');
 await page.locator('#status').selectOption('ended');ok((await page.locator('#list .status-tag').allTextContents()).includes('已截止 / 结束'),'ended archive filter works');
 await page.locator('#list [data-save]').first().click();await page.locator('[data-view="saved"]').click();ok(await page.locator('#list article').count()===1,'expired saved item remains accessible');
 await page.reload();await page.locator('[data-view="saved"]').click();ok(await page.locator('#list article').count()===1,'saved survives reload');
 await page.locator('#reset').click();await page.getByRole('searchbox',{name:'搜索公告'}).fill('学位论文计划书');await page.getByRole('button',{name:'查看详情',exact:true}).first().click();
 ok(await page.locator('#detail').isVisible(),'details open');ok(page.url().includes('#notice-'),'share link generated');
 const calendarLink=page.locator('#detail .detail-actions a');ok(await calendarLink.count()===1,'dated notice has single-notice calendar');
 const ics=await page.request.get('http://127.0.0.1:8789/'+await calendarLink.getAttribute('href'));ok(ics.ok()&&(await ics.text()).includes('BEGIN:VEVENT'),'single-notice ICS downloads');
 await page.reload();ok(await page.locator('#detail').isVisible(),'share link reopens detail');await page.keyboard.press('Escape');ok(!(await page.locator('#detail').isVisible()),'Escape closes details');
 await page.locator('#reset').click();await page.getByRole('searchbox',{name:'搜索公告'}).fill('zzzz-no-such-notice');ok(await page.getByRole('heading',{name:'没有符合条件的公告'}).isVisible(),'empty search state');
 await page.locator('#reset').click();await page.locator('#status').selectOption('');await page.locator('#source').selectOption('graduate');ok(await page.locator('#list article').count()>0,'source filter');
 await page.locator('#reset').click();await page.locator('#loadMore').click();ok(await page.locator('#list article').count()===24,'load more');
 await page.locator('#tools').click();ok(await page.locator('#toolsDialog').isVisible(),'calendar and install panel opens');ok((await page.locator('#subscribeCalendar').getAttribute('href')).startsWith('webcal://'),'iPhone calendar subscription link');
 ok((await page.locator('#toolsDialog').textContent()).includes('Safari'),'iPhone install instructions');await page.keyboard.press('Escape');
 await page.locator('.source-health summary').click();ok(await page.locator('#sourceHealth .health-row').count()===data.sources.length,'per-source health is visible');
 await page.getByRole('button',{name:'收录说明 ↗'}).click();ok((await page.locator('#aboutBody').textContent()).includes('사이버보안학과'),'correct graduate department explained');await page.keyboard.press('Escape');
 for(const width of [390,320,1440]){await page.setViewportSize({width,height:900});await page.evaluate(()=>window.scrollTo(0,0));ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),width+'px no overflow');if(width===390||width===1440)await page.screenshot({path:'output/playwright/next-'+width+'.png'});}
 await page.setViewportSize({width:390,height:844});await page.locator('#theme').click();ok(await page.evaluate(()=>document.documentElement.classList.contains('dark')),'dark theme');await page.screenshot({path:'output/playwright/next-dark.png'});
 await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#list [data-detail]').first().click();ok(await page.locator('#detail').evaluate(el=>getComputedStyle(el).animationName==='none'),'reduced motion disables animation');await page.keyboard.press('Escape');
 const manifest=await (await page.request.get('http://127.0.0.1:8789/manifest.webmanifest')).json();ok(manifest.start_url==='./'&&manifest.scope==='./'&&manifest.icons.length===2,'scoped install manifest');
 const feed=await page.request.get('http://127.0.0.1:8789/notices.ics');ok(feed.ok()&&(await feed.text()).includes('BEGIN:VCALENDAR'),'calendar subscription feed available');
 await page.evaluate(()=>navigator.serviceWorker.ready);await page.reload();await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
 await page.context().setOffline(true);await page.reload();ok(await page.locator('#offline').isVisible(),'offline cache explicitly identified');ok(await page.locator('#list article').count()>0,'cached notices available offline');
 await page.context().setOffline(false);await page.reload();ok(!(await page.locator('#offline').isVisible()),'online recovery clears offline banner');
 ok(errors.length===0,'no browser runtime errors');
 await page.evaluate(()=>localStorage.removeItem('ajouNoticeSaved'));
 return {passed:checks.length,checks};
}
