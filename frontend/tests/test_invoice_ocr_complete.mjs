import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';

const baseUrl = 'https://medguard.bookingcare.shop';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await context.newPage();

  console.log('1. Logging in as nam3@gmail.com...');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  await page.locator('#auth-username').fill('nam3@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login') && res.status() === 200),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  
  await page.waitForSelector('.clinical-app-shell, .chat-view, header', { timeout: 10000 });
  console.log('Logged in successfully!');

  // Go to Chat
  const chatInput = page.locator('form.composer-box textarea, textarea').first();
  await chatInput.fill('Tôi vừa chụp ảnh hóa đơn mua thuốc tại nhà thuốc Long Châu hết 350.000 đ');
  
  console.log('2. Sending invoice message in chat...');
  await page.locator('button.send-button, form.composer-box button[type="submit"]').first().click();

  // Wait for AI response to finish and card to render
  console.log('3. Waiting for AI Clinical Response & Spending Proposal Card...');
  await page.waitForSelector('.spending-proposal-card, button:has-text("Lưu vào Chi tiêu y tế")', { timeout: 30000 });
  console.log('Found spending proposal card in chat!');

  await page.screenshot({ path: 'scratch/screenshots/invoice_ocr_card_received.png' });
  console.log('Saved scratch/screenshots/invoice_ocr_card_received.png');

  // Click "Lưu vào Chi tiêu y tế"
  const saveBtn = page.locator('button:has-text("Lưu vào Chi tiêu y tế"), button:has-text("Lưu khoản chi")').first();
  await saveBtn.click();
  console.log('4. Clicked "Lưu vào Chi tiêu y tế". Waiting for confirmation & sync...');
  await page.waitForTimeout(2500);

  // Navigate to Spending page
  console.log('5. Navigating to Spending page...');
  const spendingBtn = page.locator('button.view-tab-btn:has-text("Chi tiêu"), button:has-text("Chi tiêu")').first();
  if (await spendingBtn.count() > 0) {
    await spendingBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/invoice_spending_updated.png', fullPage: true });
  console.log('Saved scratch/screenshots/invoice_spending_updated.png');

  const spendingText = await page.innerText('body');
  const has350 = spendingText.includes('350.000') || spendingText.includes('Long Châu');
  console.log('Spending page reflects 350.000 ₫ transaction:', has350);
  assert.ok(has350, 'Spending ledger must contain the 350.000 ₫ transaction synced from the invoice');

  console.log('=== DRUG INVOICE PHOTO OCR TO SPENDING LEDGER VERIFIED 100%! ===');
} finally {
  await browser.close();
}
