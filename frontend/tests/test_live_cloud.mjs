import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';

const targetUrl = 'https://medguard.bookingcare.shop';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

console.log(`Starting CloudFront live verification on: ${targetUrl}`);

const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage']
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  const consoleErrors = [];
  page.on('pageerror', err => consoleErrors.push(err.message));

  // 1. Visit live root
  console.log('Navigating to live CloudFront web app...');
  const res = await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });
  console.log(`Page HTTP status: ${res.status()}`);
  assert.equal(res.status(), 200, 'Live page returns 200');

  // 2. Register account if not existing, then login
  console.log('Ensuring account exists on live backend...');
  await page.evaluate(async () => {
    await fetch('/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'doctor@bookingcare.shop', password: 'TestPassword1234!', consent: true })
    }).catch(() => {});
  });

  console.log('Logging in with verified account...');
  await page.locator('input[type="email"], input[name="email"]').fill('doctor@bookingcare.shop');
  await page.locator('input[type="password"], input[name="password"]').fill('TestPassword1234!');
  const loginPromise = page.waitForResponse(r => r.url().includes('/v1/auth/login'));
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  const loginRes = await loginPromise;
  console.log('Login response status:', loginRes.status());
  await page.waitForTimeout(4000);
  await page.screenshot({ path: 'scratch/screenshots/live_logged_in_dashboard.png' });
  console.log('Saved: scratch/screenshots/live_logged_in_dashboard.png');

  // 2. Click Guest login button
  console.log('Clicking guest login button...');
  const guestBtn = page.getByRole('button', { name: /Trải nghiệm ngay không cần đăng nhập/i });
  if (await guestBtn.count() > 0) {
    await guestBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'scratch/screenshots/live_main_workspace.png' });
    console.log('Saved: scratch/screenshots/live_main_workspace.png');
  }

  // 3. Check Financial Advisor View (Spending Dashboard)
  console.log('Testing Financial Advisor tab...');
  const financeBtn = page.getByRole('button', { name: /Chi tiêu|Tài chính/i });
  if (await financeBtn.count() > 0) {
    await financeBtn.first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'scratch/screenshots/live_financial_dashboard.png' });
    console.log('Saved: scratch/screenshots/live_financial_dashboard.png');
  }

  // 4. Test Clinical Chat View
  console.log('Testing Clinical Chat tab...');
  const chatBtn = page.getByRole('button', { name: /Trò chuyện|Tư vấn lâm sàng/i });
  if (await chatBtn.count() > 0) {
    await chatBtn.first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'scratch/screenshots/live_chat_view.png' });
    console.log('Saved: scratch/screenshots/live_chat_view.png');
  }

  // 4. Test Direct API Health & Services
  console.log('Verifying backend API endpoints...');
  const healthRes = await page.evaluate(async () => {
    const r = await fetch('/v1/health');
    return { ok: r.ok, status: r.status, data: await r.json() };
  });
  console.log('API /v1/health result:', healthRes);
  assert.equal(healthRes.status, 200);
  assert.equal(healthRes.data.status, 'ok');

  console.log('All live cloud tests PASSED successfully!');
} finally {
  await browser.close();
}
