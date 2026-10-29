import { chromium } from 'playwright-core';
import fs from 'fs';
import path from 'path';

const outDir = 'scratch/screenshots/redesign_check';
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  console.log('Navigating to live login page...');
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });

  console.log('Ensuring nam1 account exists...');
  await page.evaluate(async () => {
    await fetch('/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'nam1@gmail.com', password: 'Password123!', consent: true }),
    }).catch(() => {});
  });

  console.log('Logging in...');
  await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
  await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
  
  const loginPromise = page.waitForResponse((r) => r.url().includes('/v1/auth/login'));
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  const loginRes = await loginPromise;
  console.log('Login HTTP status:', loginRes.status());
  await page.waitForTimeout(3000);

  // 1. Navigate to Schedule (?view=schedule)
  console.log('Navigating to Schedule page...');
  const scheduleNavBtn = page.locator('button:has-text("Lịch khám")').first();
  await scheduleNavBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(outDir, 'live_01_schedule_timetable.png') });
  console.log('Saved live_01_schedule_timetable.png');

  // Open Schedule Shift Modal
  console.log('Opening Shift Modal...');
  const addShiftBtn = page.locator('button:has-text("Thêm ca khám"), button.timetable-empty-add-btn').first();
  if (await addShiftBtn.count() > 0) {
    await addShiftBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'live_02_schedule_modal.png') });
    console.log('Saved live_02_schedule_modal.png');
    // Close modal
    const closeBtn = page.locator('.modal-header .icon-button, button:has-text("Hủy")').first();
    if (await closeBtn.count() > 0) await closeBtn.click();
    await page.waitForTimeout(500);
  }

  // 2. Navigate to Medication (?view=medication)
  console.log('Navigating to Medication page...');
  const medNavBtn = page.locator('button:has-text("Lịch uống thuốc")').first();
  await medNavBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(outDir, 'live_03_medication_timetable.png') });
  console.log('Saved live_03_medication_timetable.png');

  // Open Medication Modal
  console.log('Opening Medication Modal...');
  const addMedBtn = page.locator('button:has-text("Thêm cữ thuốc"), button.med-empty-add-slot-btn, button.btn-primary-add').first();
  if (await addMedBtn.count() > 0) {
    await addMedBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, 'live_04_medication_modal.png') });
    console.log('Saved live_04_medication_modal.png');
  }

  console.log('All live screenshots captured successfully!');
} catch (err) {
  console.error('Error during capture:', err);
} finally {
  await browser.close();
}
