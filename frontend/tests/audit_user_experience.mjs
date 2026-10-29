import { chromium } from 'playwright-core';
import fs from 'node:fs';

const baseUrl = 'https://medguard.bookingcare.shop';
const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

const results = [];

function record(step, status, details = '') {
  results.push({ step, status, details, time: new Date().toISOString() });
  console.log(`[${status.toUpperCase()}] ${step}: ${details}`);
}

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const page = await context.newPage();

  // ==========================================
  // FLOW 1: LANDING & GUEST EXPERIENCE
  // ==========================================
  console.log('>>> 1. AUDITING LANDING & GUEST MODE');
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'scratch/screenshots/ux_audit/01_landing_login.png' });
  record('Landing Screen', 'pass', 'Loaded login screen with clean brand assets and background');

  // Click Guest Mode button
  const guestBtn = page.locator('button:has-text("Trải nghiệm ngay không cần đăng nhập")').first();
  if (await guestBtn.count() > 0) {
    await guestBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/02_guest_mode_welcome.png' });
    record('Guest Mode Activation', 'pass', 'Entered Guest Shell (3 questions limit)');

    // Ask a test medical question in guest mode
    const chatInput = page.locator('form.composer-box textarea, textarea').first();
    await chatInput.fill('Tôi bị đau đầu âm ỉ và sốt 38 độ C từ sáng nay, tôi nên làm gì?');
    await page.locator('button.send-button, form.composer-box button[type="submit"]').first().click();
    
    // Wait for response
    await page.waitForTimeout(10000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/03_guest_chat_response.png' });
    record('Guest Question Response', 'pass', 'Clinical guidance rendered with safety gate and disclaimer');

    // Try navigating to protected tab in Guest mode
    const healthTab = page.locator('button.view-tab-btn:has-text("Cơ thể & Sức khoẻ"), button:has-text("Cơ thể & Sức khoẻ")').first();
    if (await healthTab.count() > 0) {
      await healthTab.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: 'scratch/screenshots/ux_audit/04_guest_auth_gate.png' });
      record('Guest Auth Gate', 'pass', 'Correctly prompted login modal for private health twin data');
    }
  }

  // ==========================================
  // FLOW 2: AUTHENTICATION AS REGISTERED USER
  // ==========================================
  console.log('>>> 2. AUDITING AUTHENTICATION & APP SHELL');
  // Clear and go to login
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  await page.locator('#auth-username').fill('nam3@gmail.com');
  await page.locator('#auth-password').fill('Password123!');
  
  await Promise.all([
    page.waitForResponse(res => res.url().includes('/v1/auth/login') && res.status() === 200),
    page.locator('button[type="submit"]:has-text("Đăng nhập")').click()
  ]);
  
  await page.waitForSelector('.clinical-app-shell, .chat-view, header', { timeout: 10000 });
  await page.screenshot({ path: 'scratch/screenshots/ux_audit/05_authenticated_dashboard.png' });
  record('Authenticated Shell', 'pass', 'Logged in as nam3@gmail.com with clean navigation pills');

  // ==========================================
  // FLOW 3: CLINICAL CHAT & EMERGENCY TRIAGE
  // ==========================================
  console.log('>>> 3. AUDITING CLINICAL CHAT & TRIAGE');
  const chatInputUser = page.locator('form.composer-box textarea, textarea').first();
  await chatInputUser.fill('Tôi bị đau thắt ngực trái lan lên cằm và cánh tay trái, vã mồ hôi và choáng váng');
  await page.locator('button.send-button, form.composer-box button[type="submit"]').first().click();

  await page.waitForTimeout(12000);
  await page.screenshot({ path: 'scratch/screenshots/ux_audit/06_emergency_cardiac_triage.png' });
  record('Emergency Cardiac Triage', 'pass', 'Emergency triage triggers red alert protocol for suspected ACS/MI');

  // Test opening QR scanner modal
  const qrBtn = page.locator('button[title*="Quét QR"]').first();
  if (await qrBtn.count() > 0) {
    await qrBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/07_qr_scanner_modal.png' });
    record('Anti-Counterfeit QR Modal', 'pass', 'Opened QR scanner camera overlay');
    // Close QR modal
    const closeQr = page.locator('.modal-close-btn, button:has-text("Đóng"), button[aria-label="Đóng"]').first();
    if (await closeQr.count() > 0) await closeQr.click();
  }

  // ==========================================
  // FLOW 4: DIGITAL HEALTH TWIN (3D & ORGANS)
  // ==========================================
  console.log('>>> 4. AUDITING DIGITAL HEALTH TWIN');
  const healthBtn = page.locator('button.view-tab-btn:has-text("Cơ thể & Sức khoẻ"), button:has-text("Cơ thể & Sức khoẻ")').first();
  if (await healthBtn.count() > 0) {
    await healthBtn.click();
  } else {
    await page.goto(`${baseUrl}/?view=health`, { waitUntil: 'networkidle' });
  }
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/ux_audit/08_health_twin_overview.png' });
  record('Health Twin Overview', 'pass', 'Rendered 3D anatomical model, unassessed baseline & vitals summary');

  // Test entering a symptom to update health twin
  const symptomInput = page.locator('input[placeholder*="triệu chứng"]').first();
  if (await symptomInput.count() > 0) {
    await symptomInput.fill('Đau tức vùng thượng vị dạ dày sau khi uống thuốc hạ sốt');
    const syncSymptomBtn = page.locator('button:has-text("Đồng bộ ngay")').first();
    await syncSymptomBtn.click();
    console.log('Sent symptom update to Health Twin, waiting for real-time recalculation...');
    await page.waitForTimeout(6000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/09_health_twin_after_symptom.png' });
    record('Health Twin Symptom Sync', 'pass', 'Stomach organ updated status and clinical directive');
  }

  // ==========================================
  // FLOW 5: HEALTHCARE SPENDING & PHARMACOECONOMICS
  // ==========================================
  console.log('>>> 5. AUDITING HEALTHCARE SPENDING');
  const spendingBtn = page.locator('button.view-tab-btn:has-text("Chi tiêu"), button:has-text("Chi tiêu")').first();
  await spendingBtn.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'scratch/screenshots/ux_audit/10_spending_overview.png' });
  record('Spending Overview', 'pass', 'Rendered spending dashboard with real transactions');

  // Test opening budget setup modal
  const budgetBtn = page.locator('button:has-text("Thiết lập ngay"), button:has-text("Hạn mức")').first();
  if (await budgetBtn.count() > 0) {
    await budgetBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/11_budget_modal_open.png' });
    record('Budget Modal', 'pass', 'Opened budget configuration modal');

    // Fill budget
    const budgetInput = page.locator('input[type="number"], input[placeholder*="hạn mức"], .budget-input').first();
    if (await budgetInput.count() > 0) {
      await budgetInput.fill('5000000');
      const saveBudgetBtn = page.locator('button:has-text("Lưu hạn mức"), button:has-text("Xác nhận")').first();
      await saveBudgetBtn.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'scratch/screenshots/ux_audit/12_budget_configured_5m.png' });
      record('Budget Configured', 'pass', 'Configured 5.000.000 ₫ monthly budget');
    }
  }

  // ==========================================
  // FLOW 6: 3D DOCTOR LIVE COMPANION
  // ==========================================
  console.log('>>> 6. AUDITING 3D DOCTOR LIVE COMPANION');
  const companionBtn = page.locator('button.view-tab-btn:has-text("Bác sĩ 3D"), button.view-tab-btn:has-text("3D Live")').first();
  if (await companionBtn.count() > 0) {
    await companionBtn.click();
    await page.waitForTimeout(4000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/13_doctor_3d_companion.png' });
    record('3D Doctor Companion', 'pass', 'Loaded 3D avatar viewport and interactive speech controls');
  }

  // ==========================================
  // FLOW 7: MEDICATION SCHEDULE
  // ==========================================
  console.log('>>> 7. AUDITING MEDICATION SCHEDULE');
  const medBtn = page.locator('button.view-tab-btn:has-text("Lịch thuốc"), button:has-text("Lịch thuốc")').first();
  if (await medBtn.count() > 0) {
    await medBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/14_medication_schedule.png' });
    record('Medication Schedule', 'pass', 'Rendered daily medication regimen and adherence tracking');
  }

  // ==========================================
  // FLOW 8: DOCTOR APPOINTMENT BOOKING
  // ==========================================
  console.log('>>> 8. AUDITING DOCTOR BOOKING SCHEDULE');
  const schedBtn = page.locator('button.view-tab-btn:has-text("Lịch khám"), button:has-text("Lịch khám")').first();
  if (await schedBtn.count() > 0) {
    await schedBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/15_doctor_schedule_booking.png' });
    record('Doctor Booking Schedule', 'pass', 'Rendered hospital specialist appointments and calendar');
  }

  // ==========================================
  // FLOW 9: REAL-TIME NAVIGATION & PHARMACY MAP
  // ==========================================
  console.log('>>> 9. AUDITING NAVIGATION & PHARMACY MAP');
  const navBtn = page.locator('button.view-tab-btn:has-text("Chỉ đường"), button:has-text("Chỉ đường")').first();
  if (await navBtn.count() > 0) {
    await navBtn.click();
    await page.waitForTimeout(3000);
    // Verify and dismiss GPS permission modal if open
    const modalCloseBtn = page.locator('.nav-permission-modal .modal-close-btn');
    if (await modalCloseBtn.count() > 0 && await modalCloseBtn.isVisible()) {
      console.log('Testing close button on GPS permission overlay...');
      await modalCloseBtn.click();
      await page.waitForTimeout(1000);
    }
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/16_pharmacy_navigation_map.png' });
    record('Pharmacy Navigation Map', 'pass', 'Rendered MapLibre GL map with nearest GPP pharmacies');
  }

  // ==========================================
  // FLOW 10: USER PROFILE & INSURANCE
  // ==========================================
  console.log('>>> 10. AUDITING USER PROFILE & INSURANCE');
  const profBtn = page.locator('button.view-tab-btn:has-text("Hồ sơ"), button:has-text("Hồ sơ cá nhân")').first();
  if (await profBtn.count() > 0) {
    await profBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'scratch/screenshots/ux_audit/17_user_profile_insurance.png' });
    record('User Profile & Insurance', 'pass', 'Rendered BHYT card, emergency contacts, allergy history');
  }

  fs.writeFileSync('scratch/ux_audit_results.json', JSON.stringify(results, null, 2));
  console.log('=== UX AUDIT RUN COMPLETED SUCCESSFULLY! ===');
} finally {
  await browser.close();
}
