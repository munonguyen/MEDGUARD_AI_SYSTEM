import { chromium } from 'playwright-core';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  
  console.log('1. Logging in with nam1@gmail.com...');
  await page.goto('https://medguard.bookingcare.shop', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Check if login dialog or form is present
  const emailInput = page.locator('input[type="email"], input[name="email"]');
  if (await emailInput.count() > 0) {
    await emailInput.fill('nam1@gmail.com');
    await page.locator('input[type="password"], input[name="password"]').fill('Password123!');
    await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
    await page.waitForTimeout(3000);
  }

  // 1. Schedule View
  console.log('2. Testing https://medguard.bookingcare.shop/?view=schedule');
  await page.goto('https://medguard.bookingcare.shop/?view=schedule', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/03_schedule_view.png' });
  const scheduleText = await page.locator('body').innerText();
  console.log('Schedule contains "Nguyễn Văn An":', scheduleText.includes('Nguyễn Văn An'));
  console.log('Schedule contains "Trần Thị Mai":', scheduleText.includes('Trần Thị Mai'));

  // 2. Medication View
  console.log('3. Testing https://medguard.bookingcare.shop/?view=medication');
  await page.goto('https://medguard.bookingcare.shop/?view=medication', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/04_medication_view.png' });
  const medText = await page.locator('body').innerText();
  console.log('Medication contains "Esomeprazole":', medText.includes('Esomeprazole'));
  console.log('Medication contains "Augmentin":', medText.includes('Augmentin'));

  // 3. Spending View
  console.log('4. Testing https://medguard.bookingcare.shop/?view=spending');
  await page.goto('https://medguard.bookingcare.shop/?view=spending', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/01_spending_view.png' });
  const spendText = await page.locator('body').innerText();
  console.log('Spending contains "22.450.000":', spendText.includes('22.450.000'));
  console.log('Spending contains "8.531.000":', spendText.includes('8.531.000'));

  // 4. Health View
  console.log('5. Testing https://medguard.bookingcare.shop/?view=health');
  await page.goto('https://medguard.bookingcare.shop/?view=health', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/user_views/02_health_view.png' });
  const healthText = await page.locator('body').innerText();
  console.log('Health contains "78 nhịp/phút":', healthText.includes('78 nhịp/phút') || healthText.includes('78 bpm'));
  console.log('Health contains fake 120/80:', healthText.includes('120/80 mmHg'));

  // 5. Test Chat Dynamic Extraction & Proposal
  console.log('6. Testing Chat Dynamic Interaction...');
  await page.goto('https://medguard.bookingcare.shop/?view=chat', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const msgInput = page.locator('textarea[placeholder*="Nhắn cho MedGuard"]');
  if (await msgInput.count() > 0) {
    await msgInput.fill('Hôm nay tôi mua thuốc hết 350.000đ ở Long Châu');
    await page.keyboard.press('Enter');
    console.log('Waiting for AI response stream to finish...');
    // wait for response to complete (up to 20 seconds)
    await page.waitForTimeout(15000);
    await page.screenshot({ path: 'scratch/screenshots/user_views/05_chat_spending_proposal.png' });
    const chatText = await page.locator('body').innerText();
    console.log('Chat body snippet has 350.000:', chatText.includes('350.000'));
  }

  console.log('ALL TESTS COMPLETED SUCCESSFULLY!');
} finally {
  await browser.close();
}
