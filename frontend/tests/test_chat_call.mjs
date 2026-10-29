import { chromium } from 'playwright-core';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});
const page = await browser.newPage();
page.on('request', async (req) => {
  if (req.url().includes('/v1/chat') && req.method() === 'POST') {
    console.log('--- POST /v1/chat POST DATA ---');
    console.log(req.postData());
  }
});

await page.goto('https://medguard.bookingcare.shop');
await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
await page.waitForTimeout(3000);

await page.goto('https://medguard.bookingcare.shop/?view=chat');
await page.waitForTimeout(2000);

const msgInput = page.locator('textarea, input[aria-label="Tin nhắn"]');
await msgInput.fill('Hôm nay tôi mua thuốc hết 350.000đ ở Long Châu');
await page.keyboard.press('Enter');
await page.waitForTimeout(6000);

await browser.close();
