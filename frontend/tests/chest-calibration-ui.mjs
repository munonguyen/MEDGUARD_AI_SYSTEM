import { authenticatePage } from './login-helper.mjs';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const output = process.env.MEDGUARD_UI_ARTIFACT_DIR || '../artifacts/v28_chest_calibration';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
const scenarios = [
 ['chest-wall', 'Tôi đau ngực sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan', 'ROUTINE'],
 ['exertional', 'Tôi nặng ngực khi leo cầu thang, không khó thở, không vã mồ hôi, không đau lan', 'URGENT'],
 ['emergency', 'Tôi nặng ngực khi leo cầu thang, không khó thở, không vã mồ hôi, không đau lan nhưng đau kéo dài không hết khi nghỉ', 'EMERGENCY'],
];
const evidence = [];
try {
  for (const [device, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    for (const [name, question, urgency] of scenarios) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      await authenticatePage(page, baseUrl);
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
      await page.getByRole('textbox', { name: 'Tin nhắn' }).fill(question);
      const responsePromise = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST');
      await page.getByRole('button', { name: 'Gửi tin nhắn' }).click();
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      const raw = await response.json();
      assert.equal(raw.result.urgency, urgency);
      const card = page.locator('.chat-assistant:not(.pending):visible').last();
      await card.locator('.clinical-summary-copy').waitFor();
      const primary = await card.locator('.clinical-summary-copy').innerText()
        + (await card.locator('.clinical-report-body').count() ? '\n' + await card.locator('.clinical-report-body').innerText() : '');
      const words = primary.trim().split(/\s+/).length;
      assert(primary.includes('115'), 'Conditional emergency instructions must remain visible');
      if (urgency === 'URGENT') {
        assert(raw.answer.questions.length > 0);
        assert(primary.includes('nghỉ'));
      }
      if (urgency !== 'EMERGENCY') {
        assert.equal(raw.answer.clinical_hypotheses.length, 0);
        assert(!primary.includes('Bạn bị nhồi máu'));
      }
      const dimensions = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
      assert(dimensions.scroll <= dimensions.client + 1, 'Horizontal overflow');
      assert.deepEqual(errors, []);
      const screenshot = `${output}/${device}-${name}.png`;
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(document.getAnimations().filter(a => Number.isFinite(a.effect.getComputedTiming().iterations)).map(a => a.finished.catch(() => {})));
      });
      if (name === 'emergency') {
        const summary = await card.locator('.clinical-summary-copy').boundingBox();
        const scroller = await page.locator('.chat-scroll').boundingBox();
        assert(summary.y >= scroller.y - 1 && summary.y < scroller.y + scroller.height - 40,
          'Emergency action is outside initial reading viewport');
      }
      await page.screenshot({ path: screenshot, fullPage: true });
      await card.locator('details.clinical-detail-panel > summary').click();

      evidence.push({ device, question, urgency, primary_words: words, primary_text: primary,
        response: raw, screenshot, horizontal_overflow: false, console_errors: errors, details_opened: true, passed: true });
      await context.close();
    }
  }
  await writeFile(`${output}/browser_evidence.json`, JSON.stringify({
    code_sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
    browser: 'Chromium', runtime: 'real local API; no response substitution',
    word_count_scope: 'summary and primary action/safety/question sections; whitespace-separated Vietnamese words; metadata/limitations counted separately in the 60-case audit',
    passed: true, total: evidence.length, results: evidence }, null, 2));
  console.log(JSON.stringify(evidence.map(({ device, urgency, primary_words, passed }) => ({ device, urgency, primary_words, passed }))));
} finally {
  await browser.close();
}
