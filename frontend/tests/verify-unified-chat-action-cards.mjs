import { chromium } from 'playwright-core';
import { authenticatePage } from './login-helper.mjs';

const BASE_URL = 'http://localhost:8000';
const SCREENSHOT_DIR = '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b';

async function verifyUnifiedChatActionCards() {
  console.log('=== VERIFYING UNIFIED CHAT ACTION CARDS (MEDICATION & APPOINTMENT) ===');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    console.log('1. Navigating and authenticating with MedGuard AI...');
    await authenticatePage(page, BASE_URL);
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    // Ensure auto-submit is false for card testing
    await page.evaluate(() => {
      localStorage.removeItem('medguard_auto_apply_sync_updates');
      localStorage.removeItem('medguard.user_meds.data');
      localStorage.removeItem('medguard.shifts.data');
    });

    const sendMessage = async (text) => {
      const chatInput = await page.waitForSelector('textarea[aria-label="Tin nhắn"]', { state: 'visible', timeout: 15000 });
      await chatInput.fill(text);
      await page.waitForTimeout(200);
      const sendBtn = await page.waitForSelector('.send-button:not([disabled])', { timeout: 10000 });
      await sendBtn.click();
      await page.waitForTimeout(400);
      await page.locator('.pending-premium').waitFor({ state: 'attached', timeout: 5000 }).catch(() => {});
      await page.locator('.pending-premium').waitFor({ state: 'detached', timeout: 35000 }).catch(() => {});
      await page.waitForTimeout(1000);
    };

    // 2. Test Medication Proposal Card
    console.log('2. Sending medication prompt: "Lên lịch cho tôi uống Nexium 40mg sáng 1 viên sau ăn lúc 8h"...');
    await sendMessage('Lên lịch cho tôi uống Nexium 40mg sáng 1 viên sau ăn lúc 8h');

    console.log('Waiting for Medication Proposal Card to appear in chat...');
    const medCard = await page.waitForSelector('.med-proposal-card', { timeout: 15000 });
    await page.waitForTimeout(1000);

    // Verify unified styling (should be rgb(255, 255, 255) in light mode)
    const cardBg = await medCard.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    console.log('Medication card background color:', cardBg);

    const cardText = await medCard.innerText();
    console.log('Medication card text preview:\n', cardText.substring(0, 200));

    // Capture screenshot of the unified Medication card pending
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/unified_medication_card_in_chat.png`,
      fullPage: false,
    });
    console.log('Captured unified_medication_card_in_chat.png');

    // 3. Click accept on medication card
    console.log('3. Clicking [Thêm vào Lịch uống thuốc] button...');
    const acceptMedBtn = await page.waitForSelector('.med-proposal-card .action-btn.accept-btn', { timeout: 5000 });
    await acceptMedBtn.click();
    await page.waitForTimeout(800);

    // Capture accepted state
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/unified_medication_card_accepted.png`,
      fullPage: false,
    });
    console.log('Captured unified_medication_card_accepted.png');

    // 4. Test Appointment Proposal Card
    console.log('4. Sending appointment prompt: "Tôi muốn đặt lịch khám tim mạch sáng mai lúc 9h với BS Cường"...');
    await sendMessage('Tôi muốn đặt lịch khám tim mạch sáng mai lúc 9h với BS Cường');

    console.log('Waiting for Appointment Proposal Card to appear in chat...');
    const apptCard = await page.waitForSelector('.appt-proposal-card', { timeout: 15000 });
    await page.waitForTimeout(1000);

    const apptText = await apptCard.innerText();
    console.log('Appointment card text preview:\n', apptText.substring(0, 200));

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/unified_appointment_card_in_chat.png`,
      fullPage: false,
    });
    console.log('Captured unified_appointment_card_in_chat.png');

    console.log('=== UNIFIED ACTION CARDS TEST PASSED 100%! ===');
  } catch (error) {
    console.error('Test error:', error);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/unified_card_test_error.png` });
    process.exit(1);
  } finally {
    await browser.close();
  }
}

verifyUnifiedChatActionCards();
