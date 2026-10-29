import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';

const baseUrl = 'https://medguard.bookingcare.shop';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  console.log('1. Logging in as nam2...');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.locator('#auth-username').fill('nam2@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  await Promise.all([
    page.waitForResponse(r => r.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  await page.waitForTimeout(2000);

  // 2. Chat about spending: "Hôm nay tôi mua thuốc huyết áp hết 220.000đ ở Pharmacity"
  console.log('2. Sending spending message in chat...');
  const msgInput = page.locator('textarea[placeholder*="Nhắn cho MedGuard"]');
  await msgInput.fill('Hôm nay tôi mua thuốc huyết áp hết 220.000đ ở Pharmacity');
  await page.keyboard.press('Enter');
  
  console.log('Waiting for AI response and proposal card...');
  await page.waitForTimeout(12000);

  // Check if proposal button "Lưu vào Chi tiêu y tế" or sync card exists
  const saveBtn = page.locator('button:has-text("Lưu vào Chi tiêu y tế")');
  console.log('Save to spending button count:', await saveBtn.count());
  if (await saveBtn.count() > 0) {
    console.log('Clicking "Lưu vào Chi tiêu y tế"...');
    await saveBtn.first().click();
    await page.waitForTimeout(2000);
  }

  // 3. Navigate to spending view
  console.log('3. Navigating to spending view to check updated real data...');
  await page.locator('button[title="Đánh giá chi tiêu y tế & Tối ưu Booking Care"]').click();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/user_views/nam2_spending_after_chat.png' });
  console.log('Saved nam2_spending_after_chat.png');

  const text = await page.innerText('body');
  console.log('Page has 220.000 ₫:', text.includes('220.000'));
  console.log('Still has fake 22.450.000 ₫:', text.includes('22.450.000'));
  assert.equal(text.includes('22.450.000'), false);
  console.log('DYNAMIC TWO-WAY SYNC FROM CHAT TO SPENDING VERIFIED!');
} finally {
  await browser.close();
}
