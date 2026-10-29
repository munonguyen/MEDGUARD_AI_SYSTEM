import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });

  // Login
  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  await page.waitForTimeout(2000);

  // 1. Medication View
  console.log('Capturing Medication view...');
  await page.locator('button[title="Lịch uống thuốc"]').click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/04_medication_view.png' });
  console.log('Captured 04_medication_view.png');

  // 2. Spending View
  console.log('Capturing Spending view...');
  await page.locator('button[title="Đánh giá chi tiêu y tế & Tối ưu Booking Care"]').click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/01_spending_view.png' });
  console.log('Captured 01_spending_view.png');

  // 3. Health View
  console.log('Capturing Health view...');
  await page.locator('button[title="Chuẩn đoán & Bản đồ Cơ thể Giải phẫu Real-time"]').click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/02_health_view.png' });
  console.log('Captured 02_health_view.png');

  console.log('All views successfully captured!');
} finally {
  await browser.close();
}
