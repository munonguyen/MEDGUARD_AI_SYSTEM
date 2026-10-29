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
  
  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  const [response] = await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  console.log('Login status:', response.status());
  await page.waitForTimeout(3000);
  console.log('Post-login URL:', page.url());

  // 1. Check schedule view & modal
  console.log('Navigating to schedule view...');
  await page.goto('https://medguard.bookingcare.shop/?view=schedule', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(outDir, '03_schedule_timetable.png') });
  console.log('Saved 03_schedule_timetable.png');

  // Open shift modal
  console.log('Opening schedule shift modal...');
  const addShiftBtn = page.locator('button.btn-primary-shift, button.timetable-empty-add-btn, button:has-text("Thêm ca khám")').first();
  console.log('Found shift button:', await addShiftBtn.count());
  if (await addShiftBtn.count() > 0) {
    await addShiftBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, '04_schedule_modal.png') });
    console.log('Saved 04_schedule_modal.png');
    // Close modal
    const closeShiftBtn = page.locator('.modal-header .icon-button, button.btn-secondary').first();
    if (await closeShiftBtn.count() > 0) await closeShiftBtn.click();
    await page.waitForTimeout(500);
  }

  // 2. Check medication view & modal
  console.log('Navigating to medication view...');
  await page.goto('https://medguard.bookingcare.shop/?view=medication', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(outDir, '01_medication_timetable.png') });
  console.log('Saved 01_medication_timetable.png');

  // Open medication modal
  console.log('Opening medication modal...');
  const addMedBtn = page.locator('button.btn-primary-add, button.btn-quick-add-slot, button.med-empty-add-slot-btn, button:has-text("Thêm cữ thuốc")').first();
  console.log('Found med button:', await addMedBtn.count());
  if (await addMedBtn.count() > 0) {
    await addMedBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outDir, '02_medication_modal.png') });
    console.log('Saved 02_medication_modal.png');
  }

  console.log('All verification screenshots captured successfully!');
} catch (err) {
  console.error('Error during verification:', err);
} finally {
  await browser.close();
}
