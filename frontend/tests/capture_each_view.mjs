import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });

  // Fill login
  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  const [response] = await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);

  console.log('Login status:', response.status());
  const body = await response.json();
  console.log('Login response:', body);

  await page.waitForTimeout(3000);
  console.log('URL after login:', page.url());

  // Click on "Lịch khám" button in topbar
  console.log('Clicking on Lịch khám...');
  const scheduleBtn = page.locator('button[title="Lịch khám bác sĩ"]');
  console.log('Schedule button found:', await scheduleBtn.count());
  if (await scheduleBtn.count() > 0) {
    await scheduleBtn.click();
    await page.waitForTimeout(3000);
    console.log('Current URL after click:', page.url());
    await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png' });
    console.log('Saved 03_schedule_view.png successfully!');
  }

  // Click on "Lịch thuốc"
  console.log('Clicking on Lịch thuốc...');
  const medBtn = page.locator('button[title="Lịch uống thuốc"]');
  console.log('Med button found:', await medBtn.count());
  if (await medBtn.count() > 0) {
    await medBtn.click();
    await page.waitForTimeout(3000);
    console.log('Current URL after click:', page.url());
    await page.screenshot({ path: 'scratch/screenshots/user_views/04_medication_view.png' });
    console.log('Saved 04_medication_view.png successfully!');
  }

  // Click on "Chi tiêu y tế"
  console.log('Clicking on Chi tiêu y tế...');
  const spendBtn = page.locator('button[title="Chi tiêu & Tiết kiệm Care"]');
  console.log('Spend button found:', await spendBtn.count());
  if (await spendBtn.count() > 0) {
    await spendBtn.click();
    await page.waitForTimeout(3000);
    console.log('Current URL after click:', page.url());
    await page.screenshot({ path: 'scratch/screenshots/user_views/01_spending_view.png' });
    console.log('Saved 01_spending_view.png successfully!');
  }

  // Click on "Cơ thể & Sức khoẻ"
  console.log('Clicking on Cơ thể & Sức khoẻ...');
  const healthBtn = page.locator('button:has-text("Cơ thể & Sức khoẻ")').first();
  console.log('Health button found:', await healthBtn.count());
  if (await healthBtn.count() > 0) {
    await healthBtn.click();
    await page.waitForTimeout(3000);
    console.log('Current URL after click:', page.url());
    await page.screenshot({ path: 'scratch/screenshots/user_views/02_health_view.png' });
    console.log('Saved 02_health_view.png successfully!');
  }

} finally {
  await browser.close();
}
