import { chromium } from 'playwright-core';

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function captureAll() {
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu-rasterization']
  });

  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8000/?view=companion');
  await page.waitForFunction(() => window.__companionEngine?.isVrmLoaded, { timeout: 25000 });

  for (const [personaBtn, prefix] of [['BS. Minh Tuấn', 'tuan'], ['BS. Thanh Mai', 'mai']]) {
    console.log(`\n=== Testing ${personaBtn} ===`);
    await page.getByRole('button', { name: personaBtn, exact: true }).click();
    await page.waitForTimeout(2500);
    await page.waitForFunction(() => window.__companionEngine?.isVrmLoaded, { timeout: 15000 });

    // 1. Idle Screenshot
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `scripts/${prefix}-idle.png` });
    console.log(`Saved scripts/${prefix}-idle.png`);

    // 2. Start speaking utterance
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.motion?.startUtterance('Chào bạn, tôi là bác sĩ đồng hành. Bạn đang gặp phải triệu chứng gì?');
      e.startSpeaking();
    });

    await page.waitForTimeout(2800);
    await page.screenshot({ path: `scripts/${prefix}-speaking.png` });
    console.log(`Saved scripts/${prefix}-speaking.png`);

    // 3. Stop speaking & return to rest
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.stopSpeaking();
    });

    await page.waitForTimeout(2000);
    await page.screenshot({ path: `scripts/${prefix}-returned-rest.png` });
    console.log(`Saved scripts/${prefix}-returned-rest.png`);
  }

  await browser.close();
}

captureAll().catch(console.error);
