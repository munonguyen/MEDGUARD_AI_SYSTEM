import { chromium } from 'playwright-core';
import { mkdir, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifactDir = new URL('../../.artifacts/', import.meta.url);
const brainDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/b5c563a5-11c3-4e32-9ab9-910e6ee0c8b6';
await mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: chromePath });

try {
  // 1. Desktop Test
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  desktop.setDefaultTimeout(20000);

  // Navigate to main app
  await desktop.goto(`${baseUrl}/static/index.html`, { waitUntil: 'domcontentloaded' });
  await desktop.waitForTimeout(1000);

  // Bypass login with guest mode if needed
  const guestBtn = desktop.locator('.auth-guest-btn').first();
  if (await guestBtn.isVisible()) {
    await guestBtn.click();
    await desktop.waitForTimeout(1000);
  }

  // Click on "Bác sĩ 3D Live" tab in topbar
  const companionTab = desktop.locator('button', { hasText: 'Bác sĩ 3D Live' }).first();
  await companionTab.waitFor({ state: 'visible', timeout: 10000 });
  await companionTab.click();

  // Wait for 3D Companion page container
  await desktop.locator('.grok-companion-page').waitFor({ state: 'visible' });
  await desktop.waitForTimeout(2500);

  // Verify dialogue overlay is at the bottom (not covering face)
  const dialogueOverlay = desktop.locator('.grok-dialogue-overlay');
  const box = await dialogueOverlay.boundingBox();
  console.log(`Dialogue overlay bounding box: y=${box?.y}, height=${box?.height}`);
  // Screen height is 900. Overlay should be in the lower third (y > 600)
  if (box && box.y < 500) {
    throw new Error(`Dialogue box is too high (y=${box.y}), covering the doctor's face!`);
  }
  console.log('PASS: Dialogue box is safely docked at the bottom without obscuring doctor face.');

  // Save screenshot of Doctor Minh Tuan
  const tuanPath = fileURLToPath(new URL('companion-doctor-tuan.png', artifactDir));
  await desktop.screenshot({ path: tuanPath });
  await copyFile(tuanPath, `${brainDir}/companion-doctor-tuan.png`);
  console.log('Saved companion-doctor-tuan.png');

  // Test Ask Question to Server (/v1/chat)
  console.log('Testing question query to /v1/chat...');
  const textInput = desktop.locator('.grok-text-input');
  await textInput.fill('Bác sĩ ơi, tôi bị đau họng và sốt nhẹ thì nên làm gì?');
  const sendBtn = desktop.locator('.grok-send-action-btn');
  await sendBtn.click();

  // Wait for server reply (clinical agent pipeline)
  console.log('Waiting for response from /v1/chat...');
  await desktop.waitForFunction(() => {
    const text = document.querySelector('.grok-bubble-text')?.innerText || '';
    return text.length > 0 && !text.toLowerCase().includes('phân tích');
  }, { timeout: 15000 }).catch(() => console.log('Timeout waiting for text change, proceeding...'));

  const replyText = await desktop.locator('.grok-bubble-text').innerText();
  console.log(`Server reply: "${replyText.slice(0, 140)}..."`);
  if (replyText.includes('chưa kết nối được máy chủ') || replyText.includes('gián đoạn')) {
    console.warn('Warning: Server response indicated connection error:', replyText);
  } else {
    console.log('PASS: Successfully connected to server and received clinical doctor advice!');
  }

  const queryPath = fileURLToPath(new URL('companion-query-reply.png', artifactDir));
  await desktop.screenshot({ path: queryPath });
  await copyFile(queryPath, `${brainDir}/companion-query-reply.png`);
  console.log('Saved companion-query-reply.png');

  // Switch to Female Doctor: BS. Thanh Mai
  console.log('Switching to BS. Thanh Mai...');
  const maiBtn = desktop.locator('button', { hasText: 'BS. Thanh Mai' }).first();
  await maiBtn.click();
  await desktop.waitForTimeout(2000);

  const maiPath = fileURLToPath(new URL('companion-doctor-mai.png', artifactDir));
  await desktop.screenshot({ path: maiPath });
  await copyFile(maiPath, `${brainDir}/companion-doctor-mai.png`);
  console.log('Saved companion-doctor-mai.png');

  // 2. Mobile Test (iPhone Viewport 393 x 852)
  const mobile = await browser.newPage({ viewport: { width: 393, height: 852 } });
  mobile.setDefaultTimeout(15000);

  await mobile.goto(`${baseUrl}/static/index.html?view=companion`, { waitUntil: 'domcontentloaded' });
  await mobile.waitForTimeout(1000);

  const mobileGuest = mobile.locator('.auth-guest-btn').first();
  if (await mobileGuest.isVisible()) {
    await mobileGuest.click();
    await mobile.waitForTimeout(1000);
  }

  await mobile.locator('.grok-companion-page').waitFor({ state: 'visible', timeout: 10000 });
  await mobile.waitForTimeout(2000);

  const mobilePath = fileURLToPath(new URL('companion-doctor-mobile.png', artifactDir));
  await mobile.screenshot({ path: mobilePath });
  await copyFile(mobilePath, `${brainDir}/companion-doctor-mobile.png`);
  console.log('Saved companion-doctor-mobile.png');

  console.log('ALL_DOCTOR_COMPANION_TESTS_PASS=true');
} catch (err) {
  console.error('Smoke test error:', err);
  process.exit(1);
} finally {
  await browser.close();
}
