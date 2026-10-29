import { chromium } from 'playwright-core';

const baseUrl = 'https://medguard.bookingcare.shop';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  console.log('Logging in nam1...');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
  await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForTimeout(3000);

  // Navigate by clicking the tab "Lịch khám"
  console.log('Clicking "Lịch khám" button...');
  const scheduleNavBtn = page.locator('button.view-tab-btn:has-text("Lịch khám"), button.nav-link-btn:has-text("Lịch khám")').first();
  await scheduleNavBtn.click();
  await page.waitForTimeout(3000);

  console.log('Current URL:', page.url());
  const scheduleElem = page.locator('.schedule-page-view');
  console.log('schedule-page-view count:', await scheduleElem.count());
  
  await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png' });
  console.log('Saved 03_schedule_view.png');

  // Also do medication
  console.log('Clicking "Lịch thuốc" button...');
  const medNavBtn = page.locator('button.view-tab-btn:has-text("Lịch thuốc"), button.nav-link-btn:has-text("Lịch uống thuốc")').first();
  await medNavBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/04_medication_view.png' });
  console.log('Saved 04_medication_view.png');

  // Also do spending
  console.log('Clicking "Chi tiêu y tế" button...');
  const spendNavBtn = page.locator('button.view-tab-btn:has-text("Chi tiêu y tế"), button.nav-link-btn:has-text("Chi tiêu & Tiết kiệm Care")').first();
  await spendNavBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/01_spending_view.png' });
  console.log('Saved 01_spending_view.png');

  // Also do health
  console.log('Clicking "Cơ thể & Sức khoẻ" button...');
  const healthNavBtn = page.locator('button.view-tab-btn:has-text("Cơ thể & Sức khoẻ"), button.nav-link-btn:has-text("Cơ thể & Sức khoẻ")').first();
  await healthNavBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/02_health_view.png' });
  console.log('Saved 02_health_view.png');

} finally {
  await browser.close();
}
