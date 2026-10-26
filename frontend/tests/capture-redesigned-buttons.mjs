import { chromium } from 'playwright-core';
import { authenticatePage } from './login-helper.mjs';

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('1. Authenticating...');
  await authenticatePage(page, 'http://localhost:8000');
  await page.goto('http://localhost:8000/?view=health', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  console.log('2. Waiting for 3D body silhouette panel...');
  const panel = await page.waitForSelector('.body-silhouette-panel', { timeout: 15000 });
  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  // Take a focused screenshot of the panel header & filter bar
  const header = await page.waitForSelector('.body-silhouette-panel .panel-header-bar');
  const filterBar = await page.waitForSelector('.body-silhouette-panel .system-filter-bar');

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/redesigned_3d_twin_buttons_view.png',
  });
  console.log('Captured redesigned_3d_twin_buttons_view.png');

  // Also take a clipped screenshot specifically of the 3D Anatomical card top
  const box = await panel.boundingBox();
  if (box) {
    await page.screenshot({
      path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/redesigned_buttons_zoom.png',
      clip: {
        x: Math.max(0, box.x),
        y: Math.max(0, box.y),
        width: box.width,
        height: Math.min(320, box.height)
      }
    });
    console.log('Captured redesigned_buttons_zoom.png');
  }

  await browser.close();
  console.log('Done!');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
