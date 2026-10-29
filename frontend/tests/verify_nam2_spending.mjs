import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';

const baseUrl = 'https://medguard.bookingcare.shop';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });

  console.log('1. Logging in as nam2@gmail.com...');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  // Ensure nam2 exists
  await page.evaluate(async () => {
    await fetch('/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'nam2@gmail.com', password: 'Password123!', consent: true })
    }).catch(() => {});
  });

  await page.locator('#auth-username').fill('nam2@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  await page.waitForTimeout(2000);

  // 2. Navigate to Spending View
  console.log('2. Navigating to https://medguard.bookingcare.shop/?view=spending for nam2...');
  await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/user_views/nam2_spending_clean.png' });
  console.log('Saved nam2_spending_clean.png');

  const spendingText = await page.innerText('body');
  const has22m = spendingText.includes('22.450.000');
  const has8m = spendingText.includes('8.531.000');
  console.log('Has 22.450.000 ₫:', has22m);
  console.log('Has 8.531.000 ₫:', has8m);
  assert.equal(has22m, false, 'nam2 should NEVER see 22.450.000 ₫');
  assert.equal(has8m, false, 'nam2 should NEVER see 8.531.000 ₫');

  console.log('nam2 spending baseline verification PASSED!');
} finally {
  await browser.close();
}
