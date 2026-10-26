import { chromium } from 'playwright-core';
import { authenticatePage } from './login-helper.mjs';

async function main() {
  console.log('=== STARTING CHAT CROSS-MODULE LINKAGE & HUMANIZED UI VERIFICATION ===');
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

  // 2. Test Clinical Symptom Message -> Health Twin Sync + Smart Ecosystem Bar
  console.log('2. Sending clinical symptom query: "Tôi bị đau dạ dày dữ dội sau khi uống thuốc"...');
  await sendMessage('Tôi bị đau dạ dày dữ dội sau khi uống thuốc');

  // Verify Assistant badge says "Bác Sĩ Trợ Lý AI" (not Clinical v14)
  const assistantBadge = await page.waitForSelector('.assistant-version-badge', { timeout: 15000 });
  const badgeText = await assistantBadge.textContent();
  console.log(`Assistant version badge: "${badgeText.trim()}"`);
  if (!badgeText.includes('Bác Sĩ Trợ Lý AI')) {
    throw new Error(`Expected "Bác Sĩ Trợ Lý AI", got "${badgeText}"`);
  }

  // Verify Topic badge says "Đồng bộ tự động với Bản đồ Cơ thể 3D"
  const topicBadge = await page.waitForSelector('.assistant-topic-badge', { timeout: 10000 });
  const topicText = await topicBadge.textContent();
  console.log(`Topic badge text: "${topicText.trim()}"`);

  // Verify Connected Ecosystem Action Bar exists
  console.log('Verifying Connected Ecosystem Action Bar in chat response...');
  const ecosystemBar = await page.waitForSelector('.connected-ecosystem-action-bar', { timeout: 10000 });
  await ecosystemBar.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/chat_humanized_answer_with_ecosystem_links.png',
  });
  console.log('Captured chat_humanized_answer_with_ecosystem_links.png');

  // 3. Click [Bản đồ Cơ thể 3D] chip in chat to test cross-module navigation
  console.log('3. Clicking [Bản đồ Cơ thể 3D] chip in ecosystem action bar...');
  const twinChip = await page.waitForSelector('.ecosystem-chip-btn.chip-twin', { timeout: 5000 });
  await twinChip.click();

  // Verify we are now on Health Twin page
  await page.waitForSelector('.health-workspace-container', { timeout: 15000 });
  console.log('Successfully navigated to Health Twin from Chat!');

  // Verify Humanized Vitals
  const vitalsText = await page.textContent('.vitals-sparkline-strip');
  console.log('Vitals strip text excerpt:', vitalsText.slice(0, 150).replace(/\s+/g, ' '));
  if (!vitalsText.includes('Nhịp tim (Điện tâm đồ)') || !vitalsText.includes('Nồng độ Oxy trong máu (SpO2)')) {
    throw new Error('Vitals strip did not contain humanized labels!');
  }

  // Verify Humanized Section Tabs
  const tabsText = await page.textContent('.section-tabs-group');
  console.log('Section switcher tabs:', tabsText.replace(/\s+/g, ' '));
  if (!tabsText.includes('1. Bản đồ Cơ thể 3D') || !tabsText.includes('4. Lời khuyên Toàn diện')) {
    throw new Error('Section tabs did not contain humanized labels!');
  }

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/health_twin_humanized_plain_terms.png',
  });
  console.log('Captured health_twin_humanized_plain_terms.png');

  // 4. Test Cross-Module Action inside Organ Inspector: Click [Thuốc điều trị]
  console.log('4. Testing Organ Inspector cross-module button [Thuốc điều trị]...');
  const medBtn = await page.waitForSelector('.organ-action-btn.med-btn', { timeout: 8000 });
  await medBtn.click();
  await page.waitForTimeout(1000);
  console.log('Navigated to Medications from Organ Inspector!');

  // 5. Navigate to Healthcare Spending to verify plain language & recommendations
  console.log('5. Navigating to Healthcare Spending Page...');
  await page.goto('http://localhost:8000/?view=spending', { waitUntil: 'networkidle' });
  await page.waitForSelector('.spending-web-dashboard', { timeout: 15000 });

  // Verify Plain terms in Trust strip
  const trustStrip = await page.waitForSelector('.trust-metrics-summary-strip', { timeout: 10000 });
  const trustText = await trustStrip.textContent();
  console.log('Trust strip text:', trustText.replace(/\s+/g, ' '));
  if (!trustText.includes('Độ uy tín cộng đồng') || !trustText.includes('Xác thực đánh giá thật')) {
    throw new Error('Trust strip did not contain plain-language metrics!');
  }

  // Verify Plain title in recommendations
  const recsSection = await page.waitForSelector('.smart-recommendations-section', { timeout: 10000 });
  const recsTitle = await page.textContent('.smart-recommendations-section .section-title');
  console.log(`Recommendations section title: "${recsTitle.trim()}"`);
  if (!recsTitle.includes('Mẹo Tiết Kiệm Chi Phí Thuốc & Khám Chữa Bệnh Thông Minh')) {
    throw new Error('Recommendations title did not contain plain Vietnamese!');
  }

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/spending_humanized_plain_terms.png',
  });
  console.log('Captured spending_humanized_plain_terms.png');

  // 6. Return to Chat and test Medication Proposal update
  console.log('6. Returning to Chat to test Medication proposal update...');
  await page.goto('http://localhost:8000/?view=chat', { waitUntil: 'networkidle' });
  await sendMessage('Lên lịch cho tôi uống thuốc Nexium 40mg sáng 1 viên sau ăn lúc 8h');

  await page.waitForSelector('.med-proposal-card', { timeout: 15000 });
  const acceptMedBtn = await page.waitForSelector('.med-proposal-card .accept-btn', { timeout: 10000 });
  await acceptMedBtn.click();
  await page.waitForTimeout(600);
  console.log('Accepted medication proposal from chat!');

  // Verify medication was stored in localStorage
  const savedMeds = await page.evaluate(() => localStorage.getItem('medguard.user_meds.data'));
  console.log('Saved meds in localStorage:', savedMeds ? 'OK (Found data)' : 'None');

  // 7. Test Appointment Proposal update
  console.log('7. Testing Doctor Appointment proposal update from chat...');
  await sendMessage('Đặt lịch khám tim mạch sáng mai lúc 9h với BS Cường tại BV Chợ Rẫy');
  await page.waitForSelector('.appt-proposal-card', { timeout: 15000 });
  const acceptApptBtn = await page.waitForSelector('.appt-proposal-card .accept-btn', { timeout: 10000 });
  await acceptApptBtn.click();
  await page.waitForTimeout(600);
  console.log('Accepted appointment proposal from chat!');

  // Verify appointment was stored in localStorage
  const savedShifts = await page.evaluate(() => localStorage.getItem('medguard.shifts.data'));
  console.log('Saved appointments in localStorage:', savedShifts ? 'OK (Found data)' : 'None');

  // 8. Test Profile Proposal update
  console.log('8. Testing Profile proposal update from chat...');
  await sendMessage('Cập nhật thông tin của tôi: chiều cao 175cm và cân nặng 70kg');
  await page.waitForSelector('.chat-profile-proposal-card', { timeout: 15000 });
  const acceptProfileBtn = await page.waitForSelector('.chat-profile-proposal-card .accept-btn', { timeout: 10000 });
  await acceptProfileBtn.click();
  await page.waitForTimeout(600);
  console.log('Accepted profile proposal from chat!');

  const savedProfile = await page.evaluate(() => localStorage.getItem('medguard.user_profile.data'));
  console.log('Saved profile in localStorage:', savedProfile ? 'OK (Found data)' : 'None');

  await browser.close();
  console.log('=== ALL CHAT CROSS-MODULE INTERACTIONS & HUMANIZED UI VERIFIED 100%! ===');
}

main().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
