import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  // Login first as nam1@gmail.com
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });
  await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
  await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForTimeout(3000);

  const profileData = await page.evaluate(async () => {
    const res = await fetch('/v1/health-twin/profile');
    return await res.json();
  });
  console.log('Profile from API:');
  console.log('vitals:', profileData.vitals);

  const localCache = await page.evaluate(() => {
    return localStorage.getItem('medguard_health_twin_profile');
  });
  console.log('localStorage profile cache:', localCache ? 'exists' : 'empty');
  if (localCache) {
    const parsed = JSON.parse(localCache);
    console.log('localStorage vitals:', parsed.vitals);
  }
} finally {
  await browser.close();
}
