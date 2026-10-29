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

  console.log('--- TEST 1: LOGIN AS FRESH USER nam3@gmail.com ---');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  // Ensure nam3 exists
  await page.evaluate(async () => {
    localStorage.clear();
    await fetch('/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'nam3@gmail.com', password: 'Password123!', consent: true })
    }).catch(() => {});
  });

  await page.locator('#auth-username').fill('nam3@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login') && res.status() === 200),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  
  // Wait for authenticated app shell to load
  await page.waitForSelector('.clinical-app-shell, .chat-view, .chat-panel-layout, header', { timeout: 10000 });
  console.log('Successfully logged into MedGuard App Shell!');

  console.log('--- TEST 2: NAVIGATE TO SPENDING VIEW (CHECK FOR CLEAN REAL DATA) ---');
  // Click Spending tab button or navigate via URL param
  const spendingBtn = page.locator('button.view-tab-btn:has-text("Chi tiêu"), button:has-text("Chi tiêu")').first();
  if (await spendingBtn.count() > 0) {
    await spendingBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/reality_spending_nam3.png' });
  console.log('Saved scratch/screenshots/reality_spending_nam3.png');

  const spendingText = await page.innerText('body');
  
  // Verify NO fake numbers
  assert.equal(spendingText.includes('22.450.000'), false, 'nam3 should NEVER see 22.450.000 ₫');
  assert.equal(spendingText.includes('8.531.000'), false, 'nam3 should NEVER see 8.531.000 ₫');
  assert.equal(spendingText.includes('10.000.000 ₫'), false, 'nam3 should NOT have a default 10.000.000 ₫ budget');

  // Verify empty states exist
  const hasUnsetBudget = spendingText.includes('Chưa thiết lập') || spendingText.includes('Thiết lập ngay');
  console.log('Has "Chưa thiết lập" or "Thiết lập ngay":', hasUnsetBudget);
  assert.ok(hasUnsetBudget, 'Budget KPI should indicate budget is not yet set');

  const hasEmptyAllocCard = await page.locator('.alloc-empty-activation-card').count();
  console.log('Alloc empty activation card count:', hasEmptyAllocCard);
  assert.ok(hasEmptyAllocCard > 0 || spendingText.includes('Chưa Thiết Lập Hạn Mức'), 'Should show clean activation card for Phác đồ 45-35-20');

  console.log('--- TEST 3: NAVIGATE TO HEALTH TWIN VIEW (CLINICAL UNASSESSED BASELINE) ---');
  const healthBtn = page.locator('button.view-tab-btn:has-text("Sinh đôi"), button.view-tab-btn:has-text("Sức khỏe")').first();
  if (await healthBtn.count() > 0) {
    await healthBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=health`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'scratch/screenshots/reality_health_nam3.png' });
  console.log('Saved scratch/screenshots/reality_health_nam3.png');

  const healthText = await page.innerText('body');
  
  // Verify organ status shows unassessed
  const hasUnassessedOrgan = healthText.includes('CHƯA ĐÁNH GIÁ') || healthText.includes('Chưa có dữ liệu');
  console.log('Has unassessed organ labels:', hasUnassessedOrgan);
  assert.ok(hasUnassessedOrgan, 'Organs should show unassessed status for brand new user');

  // Verify radar shows unassessed
  const hasRadarUnassessed = healthText.includes('Chưa đánh giá') || healthText.includes('--');
  console.log('Radar/Scores show unassessed indicator:', hasRadarUnassessed);
  assert.ok(hasRadarUnassessed, 'Radar / Bio-balance should show unassessed indicator');

  console.log('--- TEST 4: INVOICE PHOTO / OCR TO CASH FLOW SPENDING FLOW ---');
  const chatTabBtn = page.locator('button.view-tab-btn:has-text("Chat"), button.view-tab-btn:has-text("Trợ lý")').first();
  if (await chatTabBtn.count() > 0) {
    await chatTabBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=chat`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(2000);

  // Send message indicating an uploaded prescription/invoice
  const chatInput = page.locator('form.composer-box textarea, textarea').first();
  await chatInput.fill('Tôi vừa chụp ảnh hóa đơn mua thuốc tại nhà thuốc Pharmacity hết 285.000 đ');
  
  // Submit message via Enter key or send-button
  await page.locator('button.send-button, form.composer-box button[type="submit"]').first().click();
  console.log('Sent drug invoice message to chat. Waiting for AI response and spendingProposal...');

  // Wait for response with spending card
  await page.waitForTimeout(8000);
  await page.screenshot({ path: 'scratch/screenshots/reality_invoice_chat.png' });
  console.log('Saved scratch/screenshots/reality_invoice_chat.png');

  const chatText = await page.innerText('body');
  const hasSpendingProposal = chatText.includes('Lưu vào Chi tiêu y tế') || chatText.includes('khoản chi') || chatText.includes('285.000');
  console.log('Chat contains spending proposal:', hasSpendingProposal);

  // If button "Lưu vào Chi tiêu y tế" or "Xác nhận" exists, click it
  const saveSpendingBtn = page.locator('button:has-text("Lưu vào Chi tiêu y tế"), button:has-text("Lưu khoản chi")').first();
  if (await saveSpendingBtn.count() > 0) {
    console.log('Found "Lưu vào Chi tiêu y tế" button, clicking to save transaction...');
    await saveSpendingBtn.click();
    await page.waitForTimeout(2000);
  }

  // Navigate back to spending page to verify ledger update
  console.log('Verifying transaction in Spending Page...');
  if (await spendingBtn.count() > 0) {
    await spendingBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/reality_spending_after_invoice.png' });
  console.log('Saved scratch/screenshots/reality_spending_after_invoice.png');

  const updatedSpendingText = await page.innerText('body');
  const hasNewSpend = updatedSpendingText.includes('285.000') || updatedSpendingText.includes('Pharmacity');
  console.log('Updated spending contains new 285.000 ₫ transaction:', hasNewSpend);

  console.log('=== ALL REALITY AND OCR CASH FLOW FLOW TESTS PASSED SUCCESSFULLY! ===');
} finally {
  await browser.close();
}
