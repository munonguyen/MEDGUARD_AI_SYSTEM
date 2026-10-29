import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  console.log('1. Going to login...');
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });

  await page.locator('#auth-username').fill('nam1@gmail.com');
  await page.locator('#auth-password').fill('Password123!');

  const [res] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/v1/auth/login')),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  console.log('Login status:', res.status());

  await page.waitForTimeout(2000);

  // Check what's rendered
  console.log('Visible buttons on page:');
  const buttons = await page.$$eval('button', els => els.map(e => ({ text: e.innerText, title: e.title, class: e.className })));
  console.log('Buttons:', buttons.filter(b => b.text || b.title));

  // Check schedule button
  const scheduleBtn = page.locator('button[title="Lịch khám bác sĩ"]');
  console.log('Clicking schedule button...');
  await scheduleBtn.click();
  await page.waitForTimeout(2000);

  console.log('URL after clicking schedule:', page.url());
  const bodyHtml = await page.evaluate(() => document.body.innerHTML);
  console.log('Body HTML length:', bodyHtml.length);
  console.log('Body HTML preview:', bodyHtml.slice(0, 400));

  await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png' });
  console.log('Screenshot saved.');

} finally {
  await browser.close();
}
