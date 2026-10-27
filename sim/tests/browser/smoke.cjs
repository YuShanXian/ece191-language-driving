'use strict';
// Optional: install playwright locally, or make an existing installation visible on NODE_PATH.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.resolve(__dirname, '../results/browser-smoke');
const base = process.env.ECE191_TEST_URL || 'http://localhost:8776';
(async () => {
  if (new URL(base).port === '8775') throw Error('Use a separate test server port');
  await fs.mkdir(output, {recursive: true});
  const context = await chromium.launchPersistentContext(path.join(output, 'profile'), {
    channel: process.env.ECE191_BROWSER_CHANNEL || 'msedge', headless: true,
    viewport: {width: 1440, height: 1000},
  });
  const checks = [], errors = [];
  try {
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await page.locator('#loading').filter({hasText: 'Map ready'}).waitFor({timeout: 90000});
    assert.equal(await page.locator('#connection').innerText(), 'Service connected');
    checks.push('scene loads and service connects');
    await page.locator('[data-action="go_straight"]').click();
    await page.waitForFunction(() => /Completed/.test(document.querySelector('#pipelineRows').innerText), undefined, {timeout: 60000});
    await page.locator('#stopLive').click();
    await page.screenshot({path: path.join(output, 'driving.png'), fullPage: true});
    assert.match(await page.locator('#pipelineRows').innerText(), /Completed/);
    checks.push('direct go_straight completes in browser');
    await page.goto(base + '/review');
    await page.locator('.case-item').first().waitFor();
    assert.equal(await page.locator('.case-item').count(), 6);
    assert.match(await page.locator('#caseTitle').innerText(), /Example/);
    await page.screenshot({path: path.join(output, 'review.png'), fullPage: true});
    checks.push('review subset and first replay load');
    assert.deepEqual(errors, []);
    checks.push('no browser page errors');
    console.log(JSON.stringify({passed: checks.length, failed: 0, checks}));
  } finally {
    await context.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
