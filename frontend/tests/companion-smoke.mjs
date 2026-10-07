import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifactDir = new URL('../../.artifacts/', import.meta.url);
await mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: chromePath });

try {
  // 1. Desktop Test
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  desktop.setDefaultTimeout(15000);

  // Navigate to main app and bypass auth with guest mode
  await desktop.goto(`${baseUrl}/static/index.html`, { waitUntil: 'domcontentloaded' });
  await desktop.waitForTimeout(1000);

  // If login card is present, click guest button
  const guestBtn = desktop.locator('.auth-guest-btn').first();
  if (await guestBtn.isVisible()) {
    await guestBtn.click();
    await desktop.waitForTimeout(1000);
  }

  // Click on "Trợ lý 3D Live" tab in topbar
  const companionTab = desktop.locator('button', { hasText: 'Trợ lý 3D Live' }).first();
  await companionTab.waitFor({ state: 'visible', timeout: 10000 });
  await companionTab.click();

  // Wait for Grok Live Companion container
  await desktop.locator('.grok-companion-page').waitFor({ state: 'visible' });
  await desktop.waitForTimeout(2000);

  // Screenshot desktop
  await desktop.screenshot({ path: fileURLToPath(new URL('companion-desktop.png', artifactDir)) });
  console.log('Saved companion-desktop.png');

  // Trigger Pose: Click emotion button -> Click "Đưa tay áp má (Grok Pose)"
  const emotionBtn = desktop.locator('.grok-dock-btn[title*="Biểu cảm"]').first();
  await emotionBtn.click();
  await desktop.locator('.grok-popover-menu').waitFor({ state: 'visible' });

  const poseBtn = desktop.locator('button', { hasText: 'Đưa tay áp má' }).first();
  await poseBtn.click();
  await desktop.waitForTimeout(1000);

  await desktop.screenshot({ path: fileURLToPath(new URL('companion-pose-desktop.png', artifactDir)) });
  console.log('Saved companion-pose-desktop.png');

  // 2. Mobile Test (iPhone Viewport)
  const mobile = await browser.newPage({ viewport: { width: 393, height: 852 } }); // iPhone 14 Pro
  mobile.setDefaultTimeout(15000);

  // Navigate directly with deep link view=companion
  await mobile.goto(`${baseUrl}/static/index.html?view=companion`, { waitUntil: 'domcontentloaded' });
  await mobile.waitForTimeout(1000);

  await mobile.locator('.grok-companion-page').waitFor({ state: 'visible', timeout: 10000 });
  await mobile.waitForTimeout(2000);

  await mobile.screenshot({ path: fileURLToPath(new URL('companion-mobile.png', artifactDir)) });
  console.log('Saved companion-mobile.png');

  console.log('COMPANION_SMOKE_PASS=true');
} catch (err) {
  console.error('Smoke test error:', err);
  process.exit(1);
} finally {
  await browser.close();
}
