import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  console.log('Going to https://medguard.bookingcare.shop/?view=schedule');
  const res = await page.goto('https://medguard.bookingcare.shop/?view=schedule', { waitUntil: 'domcontentloaded' });
  console.log('HTTP Status:', res.status());

  await page.waitForTimeout(4000);
  console.log('Title:', await page.title());
  console.log('HTML snippet:', (await page.content()).slice(0, 500));

  await page.screenshot({ path: 'scratch/screenshots/user_views/debug_screen.png' });
  console.log('Debug screenshot saved.');
} finally {
  await browser.close();
}
