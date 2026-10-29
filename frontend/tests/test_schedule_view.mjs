import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  // Login first
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
  await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForTimeout(3000);

  // Navigate to schedule view
  await page.goto('https://medguard.bookingcare.shop/?view=schedule', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png' });
  console.log('Saved 03_schedule_view.png');

  // Also test chat message & proposal
  await page.goto('https://medguard.bookingcare.shop/?view=chat', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const msgInput = page.locator('textarea[placeholder*="Nhắn cho MedGuard"]');
  console.log('Found msgInput count:', await msgInput.count());
  if (await msgInput.count() > 0) {
    await msgInput.fill('Hôm nay tôi mua thuốc hết 350.000đ ở Long Châu');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(6000);
    await page.screenshot({ path: 'scratch/screenshots/user_views/05_chat_spending_proposal.png' });
    console.log('Saved 05_chat_spending_proposal.png');
  }
} finally {
  await browser.close();
}
