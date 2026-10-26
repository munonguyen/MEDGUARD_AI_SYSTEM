import { chromium } from 'playwright-core';
import { authenticatePage } from './login-helper.mjs';

async function main() {
  console.log('--- STARTING ALL CHAT INTERACTIONS E2E VERIFICATION ---');
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

  // 2. Test Medication Scheduling Proposal
  console.log('2. Testing Medication Scheduling proposal...');
  await sendMessage('Lên lịch cho tôi uống Nexium 40mg sáng 1 viên sau ăn lúc 8h');
  
  await page.waitForSelector('.med-proposal-card', { timeout: 15000 });
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_medication_proposal_pending.png' });
  console.log('Captured chat_medication_proposal_pending.png');

  // Click [Thêm vào Lịch uống thuốc]
  console.log('Clicking [Thêm vào Lịch uống thuốc] button...');
  const addMedBtn = await page.waitForSelector('.med-proposal-card .accept-btn');
  await addMedBtn.click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_medication_proposal_accepted.png' });
  console.log('Captured chat_medication_proposal_accepted.png');

  // 3. Test Doctor Appointment Booking Proposal
  console.log('3. Testing Doctor Appointment Booking proposal...');
  await sendMessage('Tôi muốn đặt lịch khám tim mạch sáng mai lúc 9h với BS Cường tại BV Chợ Rẫy');
  
  await page.waitForSelector('.appt-proposal-card', { timeout: 15000 });
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_appointment_proposal_pending.png' });
  console.log('Captured chat_appointment_proposal_pending.png');

  // Click [Xác nhận Đặt lịch khám]
  console.log('Clicking [Xác nhận Đặt lịch khám] button...');
  const bookApptBtn = await page.waitForSelector('.appt-proposal-card .accept-btn');
  await bookApptBtn.click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_appointment_proposal_accepted.png' });
  console.log('Captured chat_appointment_proposal_accepted.png');

  // 4. Test Navigation / Direction Action Card
  console.log('4. Testing Navigation & Medical POI action card...');
  await sendMessage('Chỉ đường đến Bệnh viện Chợ Rẫy');
  
  await page.waitForSelector('.nav-action-card', { timeout: 15000 });
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_navigation_action_card.png' });
  console.log('Captured chat_navigation_action_card.png');

  // 5. Test Quick Navigation to Health Twin
  console.log('5. Testing Conversational Navigation: "Mở trang sức khỏe"...');
  await sendMessage('Mở trang sức khỏe');
  await page.waitForSelector('.health-workspace-container', { timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_navigated_to_health.png' });
  console.log('Captured chat_navigated_to_health.png');

  await browser.close();
  console.log('--- ALL CHAT INTERACTIONS VERIFIED SUCCESSFULLY! ---');
}

main().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
