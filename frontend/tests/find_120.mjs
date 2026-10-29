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

  // Monitor network requests on /?view=health
  page.on('response', async (res) => {
    if (res.url().includes('health-twin')) {
      console.log('Intercepted response for:', res.url());
      try {
        const json = await res.json();
        console.log('Response vitals:', json.vitals);
      } catch {}
    }
  });

  await page.goto('https://medguard.bookingcare.shop/?view=health', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const bpCardText = await page.locator('.vital-chart-card').nth(1).innerText();
  console.log('Blood pressure card innerText:');
  console.log(bpCardText);
} finally {
  await browser.close();
}
