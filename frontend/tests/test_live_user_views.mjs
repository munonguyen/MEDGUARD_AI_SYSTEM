import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';

const baseUrl = 'https://medguard.bookingcare.shop';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

await mkdir('scratch/screenshots/user_views', { recursive: true });

console.log('Launching browser to verify live deployed user views on:', baseUrl);
const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  const consoleErrors = [];
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  // 1. Login with account nam1
  console.log('Navigating to login page...');
  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 35000 });

  console.log('Registering/ensuring nam1 exists...');
  await page.evaluate(async () => {
    await fetch('/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'nam1@gmail.com', password: 'Password123!', consent: true }),
    }).catch(() => {});
  });

  console.log('Filling login form...');
  await page.locator('input[type="email"], input[name="email"]').fill('nam1@gmail.com');
  await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
  
  const loginPromise = page.waitForResponse((r) => r.url().includes('/v1/auth/login'));
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  const loginRes = await loginPromise;
  console.log('Login HTTP status:', loginRes.status());
  await page.waitForTimeout(3000);

  // 2. Test Spending View (?view=spending)
  console.log('--- Testing ?view=spending ---');
  await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/01_spending_view.png', fullPage: true });

  const spendingBodyText = await page.innerText('body');
  const hasOldHardcodedSpend = spendingBodyText.includes('22.450.000 ₫');
  const hasOldHardcodedBhyt = spendingBodyText.includes('8.531.000 ₫');
  console.log('Spending View check:');
  console.log('  - Has old hardcoded 22.450.000 ₫:', hasOldHardcodedSpend);
  console.log('  - Has old hardcoded 8.531.000 ₫:', hasOldHardcodedBhyt);
  assert.equal(hasOldHardcodedSpend, false, 'Spending page should not show fake 22.450.000 ₫');
  assert.equal(hasOldHardcodedBhyt, false, 'Spending page should not show fake 8.531.000 ₫');

  // 3. Test Health Twin View (?view=health)
  console.log('--- Testing ?view=health ---');
  await page.goto(`${baseUrl}/?view=health`, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/02_health_view.png', fullPage: true });

  const healthBodyText = await page.innerText('body');
  const hasFakeHr = healthBodyText.includes('78 nhịp/phút');
  const hasFakeBp = healthBodyText.includes('120/80 mmHg');
  console.log('Health View check:');
  console.log('  - Has fake 78 nhịp/phút:', hasFakeHr);
  console.log('  - Has fake 120/80 mmHg:', hasFakeBp);
  assert.equal(hasFakeHr, false, 'Health twin page should not show fake 78 nhịp/phút');
  assert.equal(hasFakeBp, false, 'Health twin page should not show fake 120/80 mmHg');

  // 4. Test Schedule View (?view=schedule)
  console.log('--- Testing ?view=schedule ---');
  await page.goto(`${baseUrl}/?view=schedule`, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png', fullPage: true });
  const scheduleBodyText = await page.innerText('body');
  const hasMockPatient = scheduleBodyText.includes('Nguyễn Văn An') || scheduleBodyText.includes('Trần Thị Mai');
  console.log('Schedule View check:');
  console.log('  - Has fake mock patient names:', hasMockPatient);
  assert.equal(hasMockPatient, false, 'Schedule page should not show fake mock patient names');

  // 5. Test Medication View (?view=medication)
  console.log('--- Testing ?view=medication ---');
  await page.goto(`${baseUrl}/?view=medication`, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/04_medication_view.png', fullPage: true });
  console.log('Medication View loaded and screenshot saved.');

  // 6. Test Chat Interaction syncing to Spending & Health Twin
  console.log('--- Testing Chat Interaction & Dynamic Proposal ---');
  await page.goto(`${baseUrl}/?view=chat`, { waitUntil: 'networkidle', timeout: 25000 });
  await page.waitForTimeout(2000);

  const msgInput = page.locator('textarea, input[aria-label="Tin nhắn"]');
  if (await msgInput.count() > 0) {
    console.log('Sending chat message about spending: "Hôm nay tôi mua thuốc hết 350.000đ ở Long Châu"');
    await msgInput.fill('Hôm nay tôi mua thuốc hết 350.000đ ở Long Châu');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: 'scratch/screenshots/user_views/05_chat_spending_proposal.png' });
    console.log('Chat proposal screenshot saved.');
  }

  console.log('Verification finished successfully!');
} finally {
  await browser.close();
}
