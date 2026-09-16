import { chromium } from 'playwright-core';
import path from 'path';

const artifactDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/ca438623-6843-4532-9774-b4f6b7c32e26';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await page.goto('http://127.0.0.1:8000');
  await page.waitForLoadState('networkidle');

  // Navigate to Lịch Khám
  await page.locator('.topbar-actions').getByRole('button', { name: 'Lịch khám' }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(artifactDir, 'ui-lich-kham-fixed.png') });
  console.log('Saved ui-lich-kham-fixed.png');

  // Navigate to Lịch Uống Thuốc
  await page.locator('.sidebar-actions').getByRole('button', { name: 'Lịch uống thuốc' }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(artifactDir, 'ui-lich-uong-thuoc-page.png') });
  console.log('Saved ui-lich-uong-thuoc-page.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
