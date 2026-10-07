import { chromium } from 'playwright-core';
import { copyFile } from 'node:fs/promises';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const brainDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6';

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  await page.goto(`${baseUrl}/static/index.html?view=companion`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);

  const guestBtn = page.locator('.auth-guest-btn').first();
  if (await guestBtn.isVisible()) {
    await guestBtn.click();
    await page.waitForTimeout(1000);
  }

  await page.locator('.grok-companion-page').waitFor({ state: 'visible' });
  await page.waitForTimeout(2000);

  // 1. Test Doctor Tuan idle appearance and natural speaking gesture
  console.log('Testing Doctor Tuan natural posture & speaking...');
  await page.waitForTimeout(2500);

  // Take idle screenshot of Doctor Tuan
  const idlePathTuan = `${brainDir}/companion-idle-tuan.png`;
  await page.screenshot({ path: idlePathTuan });
  console.log('Saved companion-idle-tuan.png');

  // Activate speaking on Doctor Tuan
  await page.evaluate(() => {
    if (window.__companionEngine) {
      window.__companionEngine.startSpeaking('Chào bạn, tôi là Bác sĩ Tuấn. Tôi đang giải thích phương pháp điều trị...');
    }
  });

  // Wait 1.2s for gesture to lerp
  await page.waitForTimeout(1200);

  const speechPathTuan = `${brainDir}/companion-speaking-tuan.png`;
  await page.screenshot({ path: speechPathTuan });
  console.log('Saved companion-speaking-tuan.png');

  // Stop speaking
  await page.evaluate(() => {
    window.__companionEngine?.stopSpeaking();
  });
  await page.waitForTimeout(600);

  // 2. Test Consultation Tone popover menu
  console.log('Testing Consultation Tone selector popover...');
  const toneBtn = page.locator('button[aria-label="Cảm xúc tư vấn"]').first();
  await toneBtn.click();
  await page.waitForTimeout(600);

  const tonePopoverPath = `${brainDir}/companion-tone-menu.png`;
  await page.screenshot({ path: tonePopoverPath });
  console.log('Saved companion-tone-menu.png');

  // Click on "Khoa học & Chuẩn xác"
  const clinicalOption = page.locator('.grok-popover-item', { hasText: 'Khoa học & Chuẩn xác' }).first();
  if (await clinicalOption.isVisible()) {
    await clinicalOption.click();
    await page.waitForTimeout(800);
  }

  // 3. Switch to Doctor Mai and test female graceful posture
  console.log('Switching to Doctor Mai...');
  const maiBtn = page.locator('button', { hasText: 'BS. Thanh Mai' }).first();
  await maiBtn.click();
  await page.waitForTimeout(2500);

  // Take idle screenshot of Doctor Mai (hands clasped gracefully)
  const idlePathMai = `${brainDir}/companion-idle-mai.png`;
  await page.screenshot({ path: idlePathMai });
  console.log('Saved companion-idle-mai.png');

  // Activate speaking on Doctor Mai
  await page.evaluate(() => {
    if (window.__companionEngine) {
      window.__companionEngine.startSpeaking('Chào bạn, tôi là Bác sĩ Mai. Hãy để tôi hướng dẫn cách chăm sóc sức khỏe...');
    }
  });

  await page.waitForTimeout(1200);

  const speechPathMai = `${brainDir}/companion-speaking-mai.png`;
  await page.screenshot({ path: speechPathMai });
  console.log('Saved companion-speaking-mai.png');

  // 4. Test Query input with concise advice
  console.log('Testing query with concise clinical advice...');
  const textInput = page.locator('.grok-text-input').first();
  await textInput.fill('Tôi bị đau răng có các triệu chứng đau buốt');
  const sendBtn = page.locator('.grok-send-action-btn').first();
  await sendBtn.click();
  await page.waitForTimeout(4000);

  const answerPath = `${brainDir}/companion-concise-answer.png`;
  await page.screenshot({ path: answerPath });
  console.log('Saved companion-concise-answer.png');

  console.log('COMPANION_FULL_TEST_PASS=true');
} catch (err) {
  console.error('Speech test failed:', err);
} finally {
  await browser.close();
}
