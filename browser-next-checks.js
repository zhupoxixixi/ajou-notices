'use strict';

/*
 * Browser regression checks for the Ajou Notices UI.
 *
 * Run against a local static build:
 *   const check = require('./browser-next-checks.js');
 *   const result = await check(page);
 *
 * Use a fresh Playwright browser context for each run. The checks interact with
 * localStorage and a service worker, but never submit the translation API.
 */
module.exports = async function browserNextChecks(page) {
  const checks = [];
  const errors = [];
  const assertCheck = (condition, name) => {
    if (!condition) throw new Error('FAIL: ' + name);
    checks.push(name);
  };
  const ids = selector => page.locator(selector).count();
  const detailSelector = id => '[data-detail="' + String(id).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"]';
  const readData = () => page.evaluate(() => ({
    items: window.AJOU_NOTICES.items.map(item => ({
      id: item.id,
      title: item.title,
      titleKo: item.titleKo,
      tags: item.tags || [],
      board: item.board,
      otherSources: item.otherSources || [],
      calendarFile: item.calendarFile || ''
    })),
    sources: window.AJOU_NOTICES.sources.map(source => ({ key: source.key, name: source.name }))
  }));
  const visibleIds = async () => page.locator('#list [data-detail]').evaluateAll(elements =>
    Array.from(new Set(elements.map(element => element.getAttribute('data-detail'))))
  );
  const countValue = async () => {
    const text = await page.locator('#count').textContent();
    const match = String(text).match(/\d+/);
    return match ? Number(match[0]) : NaN;
  };
  const baseURL = /^https?:/.test(page.url()) ? new URL('.', page.url()).href : 'http://127.0.0.1:8789/';
  const pageErrors = event => errors.push(String(event && event.message || event));
  page.on('pageerror', pageErrors);
  await page.setDefaultTimeout(7000);
  await page.goto(baseURL, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window.AJOU_NOTICES && !!window.NoticeCore);

  let originalStorage = null;
  let offline = false;
  try {
    originalStorage = await page.evaluate(() => Object.fromEntries(
      Array.from({ length: localStorage.length }, (_, index) => {
        const key = localStorage.key(index);
        return [key, localStorage.getItem(key)];
      })
    ));
    await page.evaluate(() => {
      for (let index = localStorage.length - 1; index >= 0; index--) {
        const key = localStorage.key(index);
        if (key && (key.startsWith('ajouNotice') || key === 'noticeGlassStyle' || key === 'noticeBackgroundStyle')) localStorage.removeItem(key);
      }
      localStorage.setItem('ajouNoticeSaved', '[]');
      localStorage.setItem('ajouNoticeTheme', 'light');
      // Valid sentinel values make accidental coupling to Ajou Menu visible.
      localStorage.setItem('menuGlassStyle', 'translucent');
      localStorage.setItem('menuBackgroundStyle', 'white');
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES && !!window.NoticeCore);
    const data = await readData();
    assertCheck(data.items.length > 0, 'archive data is loaded without calling translation API');

    const expectedCurrent = await page.evaluate(() => {
      const now = Date.now();
      return window.AJOU_NOTICES.items.filter(item => window.NoticeCore.status(item, now) !== 'ended').length;
    });
    assertCheck(await countValue() === expectedCurrent, 'default view hides ended notices using runtime dates');
    const endedIds = await page.evaluate(() => {
      const now = Date.now();
      return window.AJOU_NOTICES.items.filter(item => window.NoticeCore.status(item, now) === 'ended').map(item => item.id);
    });
    const initialIds = await visibleIds();
    assertCheck(!initialIds.some(id => endedIds.includes(id)), 'no ended notice is rendered in the default list');
    await page.locator('#status').selectOption('');
    assertCheck(await countValue() === data.items.length, 'archive view includes all current records');
    await page.locator('#status').selectOption('current');

    const topNav = page.locator('[data-view]');
    assertCheck(await topNav.count() >= 3, 'current, active, and saved navigation controls exist');
    const navBox = await topNav.first().boundingBox();
    assertCheck(!!navBox && navBox.y < (await page.evaluate(() => innerHeight)) * 0.6, 'view navigation is placed near the top of the page');
    await page.locator('[data-view="active"]').click();
    assertCheck(await page.locator('[data-view="active"]').getAttribute('aria-pressed') === 'true', 'active view can be selected');
    await page.locator('[data-view="current"]').click();

    const savedItem = endedIds.length ? data.items.find(item => item.id === endedIds[0]) : data.items[0];
    await page.locator('#status').selectOption(endedIds.length ? 'ended' : '');
    await page.locator('#search').fill(savedItem.title);
    const saveButton = page.locator('#list [data-save="' + savedItem.id + '"]');
    assertCheck(await saveButton.count() === 1, 'a notice can be selected for the saved view');
    const savedId = await saveButton.getAttribute('data-save');
    await saveButton.click();
    await page.locator('[data-view="saved"]').click();
    assertCheck((await visibleIds()).includes(savedId), 'saved view includes the selected notice');
    assertCheck(await page.locator('#list article [data-save][aria-pressed="true"]').count() === 1, 'saved state is reflected in the card');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);
    await page.locator('[data-view="saved"]').click();
    assertCheck((await visibleIds()).includes(savedId), 'saved notice persists after reload');
    await page.locator('[data-view="current"]').click();

    const titleItem = data.items[0];
    await page.locator('#status').selectOption('');
    await page.locator('#search').fill(titleItem.title);
    const matchingCard = page.locator('#list article').first();
    assertCheck(await matchingCard.count() === 1, 'search finds a record chosen from the current archive');
    const cardText = await matchingCard.innerText();
    assertCheck(!titleItem.titleKo || !cardText.includes(titleItem.titleKo), 'home cards omit the Korean original title');
    await page.locator('#reset').click();

    const calendarItem = data.items.find(item => item.calendarFile);
    assertCheck(!!calendarItem, 'archive contains a date-qualified item with an ICS file');
    await page.locator('#status').selectOption('');
    await page.locator('#search').fill(calendarItem.title);
    await page.locator(detailSelector(calendarItem.id)).first().click();
    assertCheck(await page.locator('#detail').isVisible(), 'notice detail opens');
    assertCheck(page.url().includes('#notice-' + calendarItem.id), 'detail creates a shareable deep link');
    const originalHeading = page.locator('#detail details.original-heading');
    assertCheck(await originalHeading.count() === 1, 'Korean original heading is inside a collapsible detail section');
    assertCheck(!(await originalHeading.evaluate(element => element.open)), 'Korean original heading starts collapsed');
    await originalHeading.locator('summary').click();
    assertCheck(await originalHeading.evaluate(element => element.open), 'Korean original heading can be expanded');
    const singleIcsHref = await page.locator('#detail .detail-actions a[download]').getAttribute('href');
    assertCheck(!!singleIcsHref, 'dated detail provides a single-notice ICS download');
    const singleIcsUrl = new URL(singleIcsHref, page.url());
    assertCheck(singleIcsUrl.origin === new URL(page.url()).origin, 'single-notice ICS is served by the local archive');
    const singleIcs = await page.request.get(singleIcsUrl.href);
    assertCheck(singleIcs.ok() && (await singleIcs.text()).includes('BEGIN:VEVENT'), 'single-notice ICS contains an event');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);
    assertCheck(await page.locator('#detail').isVisible(), 'share deep link reopens the matching detail');
    await page.keyboard.press('Escape');
    await page.locator('#detail').waitFor({state:'hidden'});
    assertCheck(!(await page.locator('#detail').isVisible()), 'Escape closes the detail dialog');

    await page.locator('#reset').click();
    await page.locator('#search').fill('ajou-browser-no-match-' + Date.now());
    assertCheck(await page.getByRole('heading', { name: '没有符合条件的公告' }).isVisible(), 'search shows a clear empty state');
    await page.locator('#reset').click();
    assertCheck((await page.locator('#search').inputValue()) === '', 'reset clears the search');
    assertCheck((await page.locator('#status').inputValue()) === 'current' && (await page.locator('#source').inputValue()) === '', 'reset restores default status and source filters');

    const topic = await page.locator('#topicTabs [data-topic]').evaluateAll(buttons => {
      const topics = buttons.map(button => button.getAttribute('data-topic')).filter(Boolean);
      return topics.find(value => window.AJOU_NOTICES.items.some(item => (item.tags || []).includes(value))) || '';
    });
    assertCheck(!!topic, 'archive has a populated topic filter');
    await page.locator('#status').selectOption('');
    await page.locator('#topicTabs [data-topic="' + topic.replace(/"/g, '\\"') + '"]').click();
    assertCheck(await countValue() > 0, 'topic filter returns matching records');
    await page.locator('#reset').click();

    const sourceOption = await page.locator('#source option').evaluateAll(options => {
      const values = options.map(option => option.value).filter(Boolean);
      return values.find(value => window.AJOU_NOTICES.items.some(item =>
        item.board === value || (item.otherSources || []).some(source => source.key === value)
      )) || '';
    });
    assertCheck(!!sourceOption, 'a source filter can be selected from the current archive');
    await page.locator('#status').selectOption('');
    await page.locator('#source').selectOption(sourceOption);
    assertCheck(await countValue() > 0, 'source filter returns matching records');
    await page.locator('#reset').click();
    assertCheck((await page.locator('#source').inputValue()) === '', 'reset clears source filters');

    await page.locator('#status').selectOption('');
    const beforePage = await page.locator('#list article').count();
    assertCheck(await page.locator('#loadMore').isVisible(), 'pagination control appears when more records are available');
    await page.locator('#loadMore').click();
    assertCheck(await page.locator('#list article').count() > beforePage, 'pagination reveals additional records');

    await page.locator('#toolsToggle').click();
    assertCheck(await page.locator('#toolsDialog').isVisible(), 'settings opens before theme controls are used');
    const wasDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    await page.locator('#theme').click();
    assertCheck(await page.evaluate(() => document.documentElement.classList.contains('dark')) !== wasDark, 'theme control toggles the appearance');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);
    assertCheck(await page.evaluate(() => document.documentElement.classList.contains('dark')) !== wasDark, 'theme choice persists after reload');
    await page.evaluate(() => localStorage.setItem('ajouNoticeTheme', 'light'));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);

    const toolsToggle = page.locator('#toolsToggle');
    assertCheck(await toolsToggle.count() === 1, 'top settings control exists');
    await toolsToggle.click();
    assertCheck(await page.locator('#toolsDialog').isVisible(), 'settings control opens tools dialog');
    assertCheck(await page.locator('#toolsDialog #about').count() === 1, 'collection explanation is inside settings');
    assertCheck(await page.locator('#toolsDialog #sourceHealth').count() === 1, 'source health is inside settings');
    assertCheck(await page.locator('#toolsDialog .overview, #toolsDialog #overview').count() === 1, 'archive overview is inside settings');
    const aboutOpener = page.locator('#toolsDialog #about');
    await aboutOpener.click();
    assertCheck(await page.locator('#aboutDialog').isVisible(), 'collection explanation opens from settings');
    await page.keyboard.press('Escape');
    const healthSummary = page.locator('#toolsDialog .source-health summary');
    if (await healthSummary.count()) await healthSummary.click();
    assertCheck(await page.locator('#toolsDialog #sourceHealth .health-row').count() === data.sources.length, 'settings show health for each source');

    await page.locator('#toolsDialog #tools').click();
    assertCheck(await page.locator('#toolsDialog #calendarTools').isVisible(), 'calendar button opens calendar and install options');
    const subscribe = page.locator('#toolsDialog #subscribeCalendar');
    assertCheck(await subscribe.count() === 1 && await subscribe.isVisible(), 'settings include calendar subscription');
    assertCheck((await subscribe.getAttribute('href')).startsWith('webcal://'), 'calendar subscription uses the iPhone calendar scheme');
    const feedResponse = await page.request.get(new URL('notices.ics', page.url()).href);
    assertCheck(feedResponse.ok() && (await feedResponse.text()).includes('BEGIN:VCALENDAR'), 'calendar subscription feed is available');

    const glassControls = ['#glassTransparent', '#glassTranslucent', '#glassFrosted'];
    for (const selector of glassControls) {
      const control = page.locator('#toolsDialog ' + selector);
      assertCheck(await control.count() === 1, selector + ' appearance option exists in settings');
      await control.click();
      assertCheck(await control.getAttribute('aria-pressed') === 'true', selector + ' becomes the selected glass style');
    }
    assertCheck(await page.evaluate(() => document.documentElement.dataset.noticeGlassStyle === 'frosted'), 'glass selection updates the page appearance');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);
    await page.locator('#toolsToggle').click();
    assertCheck(await page.locator('#toolsDialog #glassFrosted').getAttribute('aria-pressed') === 'true', 'glass selection persists after reload');

    const backgroundWhite = page.locator('#toolsDialog #backgroundWhite');
    const backgroundReset = page.locator('#toolsDialog #backgroundReset');
    assertCheck(await backgroundWhite.count() === 1 && await backgroundReset.count() === 1, 'white and reset background controls exist');
    await backgroundWhite.click();
    await page.waitForFunction(() => document.documentElement.dataset.noticeBackgroundStyle === 'white');
    assertCheck(await page.evaluate(() => document.documentElement.dataset.noticeBackgroundStyle) === 'white', 'white background preset is applied');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES && document.documentElement.dataset.noticeBackgroundStyle === 'white');
    await page.locator('#toolsToggle').click();
    await backgroundReset.click();
    await page.waitForFunction(() => document.documentElement.dataset.noticeBackgroundStyle !== 'white');
    assertCheck(await page.evaluate(() => document.documentElement.dataset.noticeBackgroundStyle) !== 'white', 'background reset restores the default');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES && document.documentElement.dataset.noticeBackgroundStyle !== 'white');
    assertCheck(await page.evaluate(() => document.documentElement.dataset.noticeBackgroundStyle) !== 'white', 'background reset persists after reload');
    const menuSettings = await page.evaluate(() => ({
      glass: localStorage.getItem('menuGlassStyle'),
      background: localStorage.getItem('menuBackgroundStyle')
    }));
    assertCheck(menuSettings.glass === 'translucent' && menuSettings.background === 'white', 'notice appearance controls do not overwrite Ajou Menu preferences');

    await page.keyboard.press('Escape');
    await page.locator('#reset').click();
    const refreshItem = data.items.find(item => item.title);
    await page.locator('#status').selectOption('');
    const refreshSource = refreshItem.board;
    await page.locator('#source').selectOption(refreshSource);
    await page.locator('#search').fill(refreshItem.title);
    const beforeRefreshCount = await countValue();
    const beforeRefreshIds = await visibleIds();
    await page.locator('#toolsToggle').click();
    const refreshButton = page.locator('#refreshButton');
    assertCheck(await refreshButton.count() === 1, 'manual refresh control exists');
    await page.evaluate(() => {
      window.__noticeBrowserCheckFetchCalls = 0;
      window.__noticeOriginalFetch = window.fetch;
      window.fetch = () => {
        window.__noticeBrowserCheckFetchCalls += 1;
        return Promise.reject(new TypeError('browser check simulated network failure'));
      };
    });
    await refreshButton.click();
    await page.waitForFunction(() => {
      const status = document.querySelector('#refreshStatus');
      return status && /失败|错误|无法|保留/i.test(status.textContent || '');
    }, null, { timeout: 7000 });
    assertCheck(await ids('#refreshStatus') === 1, 'refresh failure is reported in the status area');
    assertCheck((await countValue()) === beforeRefreshCount, 'refresh failure preserves the active result count');
    assertCheck(JSON.stringify(await visibleIds()) === JSON.stringify(beforeRefreshIds), 'refresh failure preserves visible notices');
    assertCheck(await page.locator('#search').inputValue() === refreshItem.title && await page.locator('#source').inputValue() === refreshSource && await page.locator('#status').inputValue() === '', 'refresh failure preserves search, source, and status filters');
    assertCheck(await page.evaluate(() => window.__noticeBrowserCheckFetchCalls > 0), 'refresh failure was simulated without contacting the translation API');

    await page.evaluate(() => { if (window.__noticeOriginalFetch) window.fetch = window.__noticeOriginalFetch;
      delete window.__noticeOriginalFetch; });
    await page.keyboard.press('Escape');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    assertCheck(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), '390px viewport has no horizontal overflow');
    await page.setViewportSize({ width: 320, height: 844 });
    await page.evaluate(() => window.scrollTo(0, 0));
    assertCheck(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), '320px viewport has no horizontal overflow');
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.evaluate(() => window.scrollTo(0, 0));
    assertCheck(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), '1440px viewport has no horizontal overflow');

    await page.emulateMedia({ reducedMotion: 'reduce' });
    const motionDurations = await page.evaluate(() => {
      const card = document.querySelector('#list article');
      if (!card) return null;
      const style = getComputedStyle(card);
      return { transition: style.transitionDuration, animation: style.animationName, animationDuration: style.animationDuration };
    });
    assertCheck(!!motionDurations && (motionDurations.transition === '0s' || motionDurations.transition.split(',').every(value => parseFloat(value) === 0)) &&
      (motionDurations.animation === 'none' || motionDurations.animationDuration.split(',').every(value => parseFloat(value) === 0)),
      'reduced-motion preference disables card animation');

    const manifestResponse = await page.request.get(new URL('manifest.webmanifest', page.url()).href);
    const manifest = await manifestResponse.json();
    assertCheck(manifestResponse.ok() && manifest.start_url === './' && manifest.scope === './', 'install manifest stays within the current project path');

    await page.evaluate(async () => { await navigator.serviceWorker.ready; });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!navigator.serviceWorker.controller, null, { timeout: 7000 });
    const registration = await page.evaluate(async () => {
      const ready = await navigator.serviceWorker.ready;
      return { scope: ready.scope, base: new URL('.', location.href).href };
    });
    assertCheck(registration.scope === registration.base, 'service worker scope is limited to this project base path');
    assertCheck(!registration.scope.includes('/ajou-menu/'), 'notice service worker cannot claim the Ajou Menu path');

    await page.context().setOffline(true);
    offline = true;
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 10000 }).catch(() => null);
    await page.waitForFunction(()=>document.querySelector('#count').textContent.includes('条'));
    assertCheck(await page.locator('#list article').count() > 0, 'cached notices remain available offline');
    assertCheck(await page.locator('#offline').isVisible(), 'offline state is identified in the interface');
    await page.context().setOffline(false);
    offline = false;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AJOU_NOTICES);
    assertCheck(!(await page.locator('#offline').isVisible()), 'online recovery clears the offline state');

    assertCheck(errors.length === 0, 'no uncaught browser runtime errors');
  } finally {
    if (offline) await page.context().setOffline(false).catch(() => {});
    if (originalStorage) {
      await page.evaluate(snapshot => {
        localStorage.clear();
        for (const [key, value] of Object.entries(snapshot)) localStorage.setItem(key, value);
      }, originalStorage).catch(() => {});
    }
    page.off('pageerror', pageErrors);
  }
  return { passed: checks.length, checks };
};
