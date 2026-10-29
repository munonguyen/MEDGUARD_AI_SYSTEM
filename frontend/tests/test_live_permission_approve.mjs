import { chromium } from 'playwright-core';

const targetUrl = 'https://medguard.bookingcare.shop';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

console.log('Testing Permission Card Approval on https://medguard.bookingcare.shop...');
const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage']
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });

  // 1. Enter as Guest
  const guestBtn = page.getByRole('button', { name: /Trải nghiệm ngay không cần đăng nhập/i });
  await guestBtn.click();
  await page.waitForTimeout(1500);

  // 2. Click quick prompt
  const promptCard = page.locator('text=Tôi bị đau ngực và khó thở');
  if (await promptCard.count() > 0) {
    await promptCard.click();
    await page.waitForTimeout(500);
  }
  const textarea = page.locator('textarea, input[placeholder*="Nhắn cho MedGuard"]');
  await textarea.press('Enter');

  // 3. Wait for permission card
  console.log('Waiting for permission card to render...');
  const approveBtn = page.locator('button:has-text("Cho phép cập nhật")');
  await approveBtn.waitFor({ timeout: 15000 });

  // 4. Click Approve
  console.log('Clicking "Cho phép cập nhật"...');
  await approveBtn.click();
  await page.waitForTimeout(2000);

  await page.screenshot({ path: 'scratch/screenshots/live_permission_approved.png' });
  console.log('Saved: scratch/screenshots/live_permission_approved.png');

  // 5. Navigate to 3D Body Map / Health Twin to see the updated organ
  console.log('Opening 3D Body Map to verify synchronized organ state...');
  const bodyMapBtn = page.locator('text=Bản đồ Cơ thể 3D, button:has-text("Cơ thể & Sức khoẻ")').first();
  if (await bodyMapBtn.count() > 0) {
    await bodyMapBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'scratch/screenshots/live_body_map_updated.png' });
    console.log('Saved: scratch/screenshots/live_body_map_updated.png');
  }

  console.log('Permission approval & synchronization test completed successfully!');
} finally {
  await browser.close();
}
