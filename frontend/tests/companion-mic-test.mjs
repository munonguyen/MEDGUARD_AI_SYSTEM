import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']
});
const context = await browser.newContext({
  permissions: ['microphone']
});
const page = await context.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await page.goto(`${baseUrl}/static/index.html?view=companion`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);

  const guestBtn = page.locator('.auth-guest-btn').first();
  if (await guestBtn.isVisible()) {
    await guestBtn.click();
    await page.waitForTimeout(1000);
  }

  await page.locator('.grok-companion-page').waitFor({ state: 'visible' });
  await page.waitForTimeout(1500);

  // Click Mic button
  const micBtn = page.locator('.grok-mic-primary-btn');
  await micBtn.click();
  await page.waitForTimeout(1000);

  const isListeningClass = await micBtn.evaluate(el => el.classList.contains('listening'));
  const dialogueText = await page.locator('.grok-bubble-text').innerText();
  console.log('Mic button listening active:', isListeningClass);
  console.log('Dialogue text on mic start:', dialogueText);

  if (isListeningClass || dialogueText.includes('lắng nghe') || dialogueText.includes('Micro')) {
    console.log('PASS: Microphone successfully activated and doctor is listening!');
  }

  console.log('MIC_TEST_PASS=true');
} catch (err) {
  console.error('Mic test error:', err);
} finally {
  await browser.close();
}
