import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const output = process.env.MEDGUARD_UI_ARTIFACT_DIR || '../artifacts/v28_adaptive_length';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
const scenarios = [
  ['sleep', 'Có nên ngủ sớm không?', 'brief'],
  ['detail', 'Giải thích chi tiết lợi ích của ngủ sớm', 'detailed'],
  ['headache', 'Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.', 'focused'],
  ['emergency', 'Trả lời ngắn thôi: tôi đau ngực lan tay trái và vã mồ hôi, có nên ngủ sớm không?', 'focused'],
  ['dental', 'Tôi đang đau răng,cần có cách nào để hết đau răng', 'focused'],
  ['muscle', 'tôi đang đâu cơ', 'focused'],
];
const evidence = [];
try {
  for (const [device, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    for (const [name, question, mode] of scenarios) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      const errors = [];
      page.on('pageerror', err => errors.push(err.message));
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
      await page.getByRole('textbox', { name: 'Tin nhắn' }).fill(question);
      const responsePromise = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST');
      await page.getByRole('button', { name: 'Gửi tin nhắn' }).click();
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      const raw = await response.json();
      assert.equal(raw.answer.presentation, mode);
      const card = page.locator('.chat-assistant:not(.pending):visible').last();
      await card.locator('.clinical-summary-copy').waitFor();
      const primary = await card.locator('.clinical-summary-copy').innerText()
        + (await card.locator('.clinical-report-body').count() ? '\n' + await card.locator('.clinical-report-body').innerText() : '');
      const words = primary.trim().split(/\s+/).length;
      if (name === 'sleep') {
        assert(words <= 80);
        assert(primary.includes('Có,'));
        assert(primary.includes('tập trung') && primary.includes('tâm trạng'));
        assert(!primary.includes('Mức phân luồng'));
        assert.equal(await card.locator('.clinical-limitations:visible').count(), 0);
      }
      if (name === 'detail') assert(words > 80);
      if (name === 'dental') {
        assert(primary.includes('nha sĩ') && primary.includes('ăn mềm'));
        assert(!primary.includes('căng cơ') && !primary.includes('RICE'));
        assert(raw.answer.sources.some(s => s.references.includes('https://www.nhs.uk/symptoms/toothache/')));
      }
      if (name === 'muscle') {
        assert(primary.includes('vùng'));
        assert(!primary.includes('thoái hóa') && !primary.includes('gối'));
        assert.equal(raw.answer.clinical_hypotheses.length, 0);
      }
      if (name === 'headache') {
        assert(!primary.includes('Tension headache'));
        assert(primary.includes('cấp cứu'));
        assert(words <= 300, 'Simple screen headache still too verbose');
      }
      if (name === 'emergency') {
        assert.equal(raw.result.urgency, 'EMERGENCY');
        assert(primary.includes('115'));
        assert.equal(raw.answer.questions.length, 0);
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
      if (name === 'headache') await card.getByText(/Tension headache/).first().waitFor();
      evidence.push({ device, question, presentation: mode, primary_words: words, primary_text: primary,
        response: raw, screenshot, horizontal_overflow: false, console_errors: errors, details_opened: true, passed: true });
      await context.close();
    }
  }
  await writeFile(`${output}/browser_evidence.json`, JSON.stringify({
    code_sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
    browser: 'Chromium', runtime: 'real local API; no response substitution',
    word_count_scope: 'summary and primary action/safety/question sections; whitespace-separated Vietnamese words; metadata/limitations counted separately in the 60-case audit',
    passed: true, total: evidence.length, results: evidence }, null, 2));
  console.log(JSON.stringify(evidence.map(({ device, presentation, primary_words, passed }) => ({ device, presentation, primary_words, passed }))));
} finally {
  await browser.close();
}
