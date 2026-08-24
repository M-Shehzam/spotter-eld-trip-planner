/**
 * Twenty-eight checks against the deployed app.
 *
 * These run in a real browser against the hosted URLs, because the assessment
 * is graded on the hosted version and a green local run proves nothing about
 * it. Every user-facing bug in this project was found by looking at a rendered
 * page while the unit tests stayed green.
 *
 * Point APP and API at localhost to check a branch before it ships.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const OUT = __dirname;
const APP = 'https://spotter-eld-trip-planner-sepia.vercel.app/';
const API = 'https://spotter-eld-api-ok80.onrender.com';
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const results = [];
const check = (n, p, d = '') => { results.push({ n, p }); console.log(`${p ? 'PASS' : 'FAIL'}  ${n}${d ? '  :: ' + d : ''}`); };

async function plan(page) {
  const fill = async (l, v) => {
    const f = page.getByLabel(l, { exact: false }).first();
    await f.click(); await f.fill(v); await page.waitForTimeout(900); await page.keyboard.press('Escape');
  };
  await fill('Current location', 'Newark, NJ');
  await fill('Pickup', 'Chicago, IL');
  await fill('Dropoff', 'Los Angeles, CA');
  await page.getByLabel(/cycle/i).first().fill('20');
  await page.getByRole('button', { name: /^plan trip$/i }).click();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1100 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));

  await page.goto(APP, { waitUntil: 'networkidle', timeout: 120000 });
  check('the hosted page loads with an empty state', await page.getByText(/no trip planned yet/i).isVisible());
  check('served over HTTPS', page.url().startsWith('https://'));

  const f = page.getByLabel('Current location', { exact: false }).first();
  await f.click(); await f.fill('chic'); await page.waitForTimeout(2500);
  check('autocomplete reaches the API across origins', (await page.getByRole('option').count()) > 0);
  await page.keyboard.press('Escape');

  await page.reload({ waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /^plan trip$/i }).click();
  await page.waitForTimeout(500);
  check('empty submit errors on each location', (await page.getByText('Required.').count()) === 3);

  await page.reload({ waitUntil: 'networkidle' });
  await page.evaluate(() => document.body.focus());
  await page.keyboard.press('Tab'); await page.waitForTimeout(400);
  const skip = await page.evaluate(() => { const e = document.activeElement; return { t: e.textContent, y: e.getBoundingClientRect().top }; });
  check('first Tab reaches a visible skip link', /skip to the plan/i.test(skip.t || '') && skip.y >= 0);

  await plan(page);
  await page.waitForSelector('svg[aria-label*="daily log"]', { timeout: 180000 });
  await page.waitForTimeout(2500);
  check('the map renders', await page.locator('.leaflet-container').isVisible());
  check('the route polyline is drawn', (await page.locator('.leaflet-overlay-pane path').count()) >= 2);
  const tabs = await page.getByRole('tab').count();
  check('a tab exists for every day', tabs > 1, `${tabs} tabs`);

  const trip = await page.evaluate(async a => (await fetch(`${a}/api/v1/trips/${new URLSearchParams(location.search).get('trip')}/`)).json(), API);
  const bad = trip.logs.map((l, i) => ({ i, s: Object.values(l.totals).reduce((x, y) => x + y, 0) })).filter(d => Math.abs(d.s - 24) > 1e-6);
  check('every sheet accounts for 24 hours', bad.length === 0, JSON.stringify(bad));
  check('the audit reports the plan compliant', trip.summary.compliant === true, JSON.stringify(trip.summary.violations));
  check('sheet mileage matches route distance', Math.abs(trip.logs.reduce((s, l) => s + l.total_miles_driving, 0) - trip.route.distance_miles) < 2,
    `${trip.logs.reduce((s, l) => s + l.total_miles_driving, 0).toFixed(1)} vs ${trip.route.distance_miles}`);
  check('the backend runs at the corrected speed factor', trip.meta.truck_speed_factor === 1.0);

  const url = page.url();
  check('the plan gets a shareable URL', /\?trip=/.test(url));
  await page.goto(url, { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForSelector('svg[aria-label*="daily log"]', { timeout: 120000 });
  await page.waitForTimeout(2000);
  const restored = {
    c: await page.getByLabel('Current location', { exact: false }).first().inputValue(),
    p: await page.getByLabel('Pickup', { exact: false }).first().inputValue(),
    d: await page.getByLabel('Dropoff', { exact: false }).first().inputValue(),
    h: await page.getByLabel(/cycle hours used/i).first().inputValue(),
  };
  check('a shared link restores the form it was planned with',
    restored.c === 'Newark, NJ' && restored.p === 'Chicago, IL' && restored.d === 'Los Angeles, CA' && Number(restored.h) === 20,
    JSON.stringify(restored));

  const cycleNote = await page.getByText(/used at arrival|used of 70 at arrival/i).count();
  check('the cycle tile says which end of the trip it counts', cycleNote > 0);

  const first = await page.locator('svg[aria-label*="daily log"]').first().getAttribute('aria-label');
  await page.getByRole('tab').nth(1).click(); await page.waitForTimeout(900);
  check('switching tabs draws a different day', first !== await page.locator('svg[aria-label*="daily log"]').first().getAttribute('aria-label'));

  const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 40000 }), page.getByRole('button', { name: /download png/i }).click()]);
  const png = OUT + '/live-export.png'; await dl.saveAs(png);
  check('the sheet exports as a PNG', fs.statSync(png).size > 50000, `${fs.statSync(png).size} bytes`);

  await page.emulateMedia({ media: 'print' }); await page.waitForTimeout(500);
  check('print carries every sheet', (await page.locator('.print-sheet').count()) === trip.logs.length);
  check('print drops the map', !(await page.locator('.leaflet-container').isVisible().catch(() => false)));
  await page.emulateMedia({ media: 'screen' });

  for (const w of [390, 768, 1024, 1600]) {
    await page.setViewportSize({ width: w, height: 900 }); await page.waitForTimeout(700);
    const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    check(`no horizontal page scroll at ${w}px`, o <= 1, `overflow ${o}px`);
  }
  await page.setViewportSize({ width: 1600, height: 1100 });

  await page.addScriptTag({ content: AXE });
  const axe = await page.evaluate(async () => (await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] })).violations.map(v => ({ id: v.id, impact: v.impact })));
  check('no serious or critical axe violations', axe.filter(v => ['critical', 'serious'].includes(v.impact)).length === 0, JSON.stringify(axe));
  await ctx.close();

  const rm = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
  const rp = await rm.newPage();
  await rp.goto(url, { waitUntil: 'networkidle', timeout: 120000 });
  await rp.waitForSelector('svg[aria-label*="daily log"]', { timeout: 120000 }); await rp.waitForTimeout(1200);
  const line = await rp.evaluate(() => { const p = document.querySelector('[data-duty-line]'); return p ? { o: getComputedStyle(p).strokeDashoffset, l: p.getTotalLength() > 0 } : null; });
  check('the duty line is fully drawn under reduced motion', line && line.l && parseFloat(line.o) === 0);
  await rm.close();

  const ec = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const ep = await ec.newPage();
  await ep.goto(APP, { waitUntil: 'networkidle', timeout: 120000 });
  await ep.route('**/api/v1/trips/', r => r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'routing_unavailable', message: 'The routing service is not answering.', detail: {} } }) }));
  await plan(ep);
  await ep.waitForSelector('#results [role="alert"]', { timeout: 40000 });
  const at = await ep.locator('#results [role="alert"]').first().innerText();
  check('a failed request shows an alert with a recovery path', /could not be planned/i.test(at) && /rate limits/i.test(at));
  check('the failure is reported once', (await ep.locator('[role="alert"]').count()) === 1);
  await ec.close();

  check('no console errors anywhere in the run', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
  const failed = results.filter(r => !r.p);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed against production`);
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('SUITE CRASHED: ' + e.message); process.exit(2); });
