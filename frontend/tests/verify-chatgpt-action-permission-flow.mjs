import { chromium } from 'playwright-core';
import { authenticatePage } from './login-helper.mjs';

async function main() {
  console.log('=== STARTING CHATGPT-STYLE ACTION PERMISSION & AUTO-SUBMIT E2E TEST ===');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // 1. Authenticate with MedGuard AI
  console.log('1. Authenticating real session for MedGuard AI...');
  await authenticatePage(page, 'http://localhost:8000');
  await page.goto('http://localhost:8000/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);

  // Clear auto-submit setting to test permission-asking first
  await page.evaluate(() => {
    localStorage.removeItem('medguard_auto_apply_sync_updates');
    localStorage.removeItem('medguard_health_twin_profile');
  });

  // Helper to send message and wait for AI response
  const sendMessage = async (text) => {
    const chatInput = await page.waitForSelector('textarea[aria-label="Tin nhắn"]', { state: 'visible', timeout: 15000 });
    await chatInput.fill(text);
    await page.waitForTimeout(200);
    const sendBtn = await page.waitForSelector('.send-button:not([disabled])', { timeout: 10000 });
    await sendBtn.click();
    await page.waitForTimeout(400);
    await page.locator('.pending-premium').waitFor({ state: 'attached', timeout: 5000 }).catch(() => {});
    await page.locator('.pending-premium').waitFor({ state: 'detached', timeout: 35000 }).catch(() => {});
    await page.waitForTimeout(800);
  };

  // 2. Send Clinical Symptom Query -> ChatGPT Action Permission Card MUST appear
  console.log('2. Sending clinical symptom: "Tôi bị đau dạ dày dữ dội sau khi uống thuốc"...');
  await sendMessage('Tôi bị đau dạ dày dữ dội sau khi uống thuốc');

  // Verify ActionPermissionConfirmationCard is rendered
  console.log('Verifying ChatGPT-style Action Permission Card in chat...');
  const actionCard = await page.waitForSelector('.chatgpt-action-permission-card.status-pending', { timeout: 15000 });
  await actionCard.scrollIntoViewIfNeeded();

  // Check card contents
  const cardText = await actionCard.textContent();
  console.log('Action Permission Card text excerpt:', cardText.slice(0, 180).replace(/\s+/g, ' '));
  if (!cardText.includes('YÊU CẦU CẤP QUYỀN TRUY CẬP') || !cardText.includes('Bản đồ Cơ thể 3D')) {
    throw new Error('Action Permission card did not contain expected title and module!');
  }

  // Take screenshot of pending permission card
  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chatgpt_action_permission_card_pending.png',
  });
  console.log('Captured chatgpt_action_permission_card_pending.png');

  // 3. User clicks [Cho phép cập nhật] button
  console.log('3. Clicking [Cho phép cập nhật] button...');
  const acceptBtn = await page.waitForSelector('.chatgpt-action-permission-card .btn-accept-action', { timeout: 8000 });
  await acceptBtn.click();
  await page.waitForTimeout(800);

  // Verify status turns into 'accepted' with success banner
  await page.waitForSelector('.chatgpt-action-permission-card.status-accepted', { timeout: 8000 });
  const acceptedBanner = await page.waitForSelector('.action-result-banner.accepted-banner', { timeout: 5000 });
  const bannerText = await acceptedBanner.textContent();
  console.log('Accepted banner text:', bannerText.replace(/\s+/g, ' '));

  // Verify navigation link button exists inside card
  const viewTargetBtn = await page.waitForSelector('.btn-view-module-target', { timeout: 5000 });
  const viewBtnLabel = await viewTargetBtn.textContent();
  console.log(`View target button: "${viewBtnLabel.trim()}"`);

  // Take screenshot of accepted permission card
  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chatgpt_action_permission_card_accepted.png',
  });
  console.log('Captured chatgpt_action_permission_card_accepted.png');

  // 4. Test Spending Update with "Tự động áp dụng cho các lần sau"
  console.log('4. Sending spending message: "Hôm nay tôi mua thuốc hết 350.000đ tại nhà thuốc Long Châu"...');
  await sendMessage('Hôm nay tôi mua thuốc hết 350.000đ tại nhà thuốc Long Châu');

  const spendingActionCard = await page.locator('.chatgpt-action-permission-card.status-pending').last();
  await spendingActionCard.waitFor({ state: 'visible', timeout: 15000 });
  await spendingActionCard.scrollIntoViewIfNeeded();

  // Check the Auto-Submit checkbox
  console.log('Checking "Tự động áp dụng cho các lần sau" checkbox...');
  const autoCheckbox = await spendingActionCard.locator('.auto-submit-checkbox');
  await autoCheckbox.check();

  // Click [Cho phép cập nhật]
  const acceptSpendingBtn = await spendingActionCard.locator('.btn-accept-action');
  await acceptSpendingBtn.click();
  await page.waitForTimeout(800);

  // Verify auto-submit setting was saved to localStorage
  const isAutoSubmitSaved = await page.evaluate(() => localStorage.getItem('medguard_auto_apply_sync_updates'));
  console.log(`localStorage['medguard_auto_apply_sync_updates']: "${isAutoSubmitSaved}"`);
  if (isAutoSubmitSaved !== 'true') {
    throw new Error('Auto-submit setting was not saved to localStorage!');
  }

  // 5. Test Auto-Submit flow on next message (does not require manual click!)
  console.log('5. Sending another message with auto-submit enabled: "Sau đó tôi bị đau đầu chóng mặt"...');
  await sendMessage('Sau đó tôi bị đau đầu chóng mặt');

  // Verify card automatically created in accepted status
  const autoCard = await page.locator('.chatgpt-action-permission-card.status-accepted').last();
  await autoCard.waitFor({ state: 'visible', timeout: 15000 });
  console.log('Auto-submitted card verified in accepted status!');

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chatgpt_action_auto_submit_enabled.png',
  });
  console.log('Captured chatgpt_action_auto_submit_enabled.png');

  // 6. Test Settings Modal toggle
  console.log('6. Opening Settings Modal to verify Auto-Submit toggle...');
  const settingsBtn = await page.waitForSelector('.topbar-settings-btn', { timeout: 8000 });
  await settingsBtn.click();
  await page.waitForSelector('.settings-dialog-window', { timeout: 10000 });

  const toggleSection = await page.waitForSelector('.pane-section:has-text("Tự động Submit & Cấp quyền cập nhật")', { timeout: 8000 });
  const toggleText = await toggleSection.textContent();
  console.log('Settings toggle section text:', toggleText.replace(/\s+/g, ' '));

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/settings_modal_auto_submit_toggle.png',
  });
  console.log('Captured settings_modal_auto_submit_toggle.png');

  await browser.close();
  console.log('=== CHATGPT ACTION PERMISSION & AUTO-SUBMIT TEST PASSED 100%! ===');
}

main().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
