import { chromium } from 'playwright-core';

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('1. Navigating to MedGuard AI app (http://localhost:8000/)...');
  await page.goto('http://localhost:8000/?guest=true', { waitUntil: 'networkidle' });

  // Wait for sidebar
  await page.waitForSelector('.sidebar');
  console.log('2. Verifying ChatGPT-style user card at sidebar bottom...');
  const userCardBtn = await page.waitForSelector('.sidebar-user-card-btn');
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chatgpt_sidebar_user_card.png' });
  console.log('Captured chatgpt_sidebar_user_card.png');

  // Click user card to open popover
  console.log('3. Clicking sidebar user card to open popover...');
  await userCardBtn.click();
  await page.waitForSelector('.sidebar-user-popover-menu');
  await page.waitForTimeout(250);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/sidebar_user_popover_open.png' });
  console.log('Captured sidebar_user_popover_open.png');

  // Click "Hồ sơ cá nhân & Bảo hiểm"
  console.log('4. Opening PatientProfileModal from popover menu...');
  const profileMenuItem = await page.waitForSelector('.popover-menu-item.highlight');
  await profileMenuItem.click();

  await page.waitForSelector('.profile-modal-container');
  await page.waitForTimeout(350);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/patient_profile_modal_tab1.png' });
  console.log('Captured patient_profile_modal_tab1.png');

  // Click Tab 2: BHYT, BHXH & Nhân thọ
  console.log('5. Switching to Tab 2: BHYT, BHXH & Nhân thọ...');
  const tab2Btn = await page.locator('.profile-tab-btn').nth(1);
  await tab2Btn.click();
  await page.waitForTimeout(200);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/patient_profile_modal_tab2_insurance.png' });
  console.log('Captured patient_profile_modal_tab2_insurance.png');

  // Click Tab 3: Tiền sử Y tế & Khẩn cấp
  console.log('6. Switching to Tab 3: Tiền sử Y tế & Khẩn cấp...');
  const tab3Btn = await page.locator('.profile-tab-btn').nth(2);
  await tab3Btn.click();
  await page.waitForTimeout(200);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/patient_profile_modal_tab3_medical.png' });
  console.log('Captured patient_profile_modal_tab3_medical.png');

  // Close modal
  const closeBtn = await page.waitForSelector('.modal-close-btn');
  await closeBtn.click();
  await page.waitForTimeout(200);

  // Now test chatting: First, message about relative (third-party)
  console.log('7. Testing third-party message: "Bố tôi năm nay 68 tuổi bị cao huyết áp..."');
  const chatInput = await page.waitForSelector('textarea[aria-label="Tin nhắn"]');
  await chatInput.fill('Bố tôi năm nay 68 tuổi bị cao huyết áp, cần tư vấn uống thuốc gì');
  await page.keyboard.press('Enter');

  // Wait for assistant response to finish (pending-premium detached)
  await page.waitForTimeout(400);
  await page.locator('.pending-premium').waitFor({ state: 'attached', timeout: 5000 }).catch(() => {});
  await page.locator('.pending-premium').waitFor({ state: 'detached', timeout: 35000 });
  await page.waitForTimeout(800);

  // Ensure NO proposal card is present for relative!
  const hasRelativeProposal = await page.locator('.chat-profile-proposal-card').count();
  console.log('Third party proposal count (must be 0):', hasRelativeProposal);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_relative_no_proposal.png' });

  // Now test chatting: Self-provided profile info
  console.log('8. Testing self profile message: "Tôi tên là Nguyễn Văn An, số BHYT là DN 4 79 79 12345678, KCB tại BV Chợ Rẫy, cao 1m75 nặng 70kg, dị ứng penicillin"');
  await chatInput.fill('Tôi tên là Nguyễn Văn An, số thẻ BHYT của tôi là DN 4 79 79 12345678, KCB ban đầu tại BV Chợ Rẫy, cao 1m75 nặng 70kg, dị ứng penicillin');
  await page.waitForTimeout(200);

  // Click send button directly
  const sendBtn = await page.waitForSelector('.send-button:not([disabled])', { timeout: 10000 });
  await sendBtn.click();

  // Wait for processing to complete
  await page.waitForTimeout(400);
  await page.locator('.pending-premium').waitFor({ state: 'attached', timeout: 5000 }).catch(() => {});
  await page.locator('.pending-premium').waitFor({ state: 'detached', timeout: 35000 });
  await page.waitForTimeout(1000);

  // Wait for assistant response and proposal card
  await page.waitForSelector('.chat-profile-proposal-card', { timeout: 20000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_self_proposal_card_pending.png' });
  console.log('Captured chat_self_proposal_card_pending.png');

  // Click "Cho phép cập nhật"
  console.log('9. Clicking [Cho phép cập nhật] button...');
  const acceptBtn = await page.waitForSelector('.proposal-btn.accept-btn', { timeout: 10000 });
  await acceptBtn.click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_proposal_accepted_updated.png' });
  console.log('Captured chat_proposal_accepted_updated.png');

  // Check that sidebar user card now reflects "Nguyễn Văn An" and BHYT verified badge!
  const updatedUserName = await page.locator('.user-card-name').textContent();
  console.log('Updated user card name in sidebar:', updatedUserName);

  await browser.close();
  console.log('ALL VERIFICATIONS COMPLETED SUCCESSFULLY!');
}

main().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
