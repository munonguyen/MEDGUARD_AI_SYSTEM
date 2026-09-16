import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';

const artifactDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/ca438623-6843-4532-9774-b4f6b7c32e26';

const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await context.newPage();

  await page.goto('http://127.0.0.1:8000', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);

  // 1. Capture the initial state and Schedule Drawer
  await page.getByRole('button', { name: 'Lịch uống thuốc', exact: true }).click();
  await page.waitForSelector('.schedule-drawer');
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${artifactDir}/ui-drawer-schedule-new.png` });
  console.log('Captured ui-drawer-schedule-new.png');

  // Test loading sample regimen
  const sampleBtn = page.getByRole('button', { name: /Tải phác đồ thuốc mẫu/i });
  if (await sampleBtn.isVisible()) {
    await sampleBtn.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${artifactDir}/ui-drawer-schedule-populated.png` });
    console.log('Captured ui-drawer-schedule-populated.png');
  }

  await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.waitForTimeout(400);

  // 2. Open Settings Modal
  await page.getByRole('button', { name: 'Cài đặt' }).first().click();
  await page.waitForSelector('.settings-dialog-window');
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${artifactDir}/ui-settings-general.png` });
  console.log('Captured ui-settings-general.png');

  // Switch to Health Profile tab
  await page.getByRole('button', { name: 'Hồ sơ sức khỏe' }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${artifactDir}/ui-settings-profile.png` });
  console.log('Captured ui-settings-profile.png');

  // Switch to Reminders tab
  await page.getByRole('button', { name: 'Nhắc nhở uống thuốc' }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${artifactDir}/ui-settings-reminders.png` });
  console.log('Captured ui-settings-reminders.png');

  // Switch to Privacy tab
  await page.getByRole('button', { name: 'Dữ liệu & Quyền riêng tư' }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${artifactDir}/ui-settings-privacy.png` });
  console.log('Captured ui-settings-privacy.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
