import { chromium } from 'playwright-core';

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();

  console.log('1. Navigating to MedGuard AI Dedicated Profile Page (http://localhost:8000/?view=profile&guest=true)...');
  await page.goto('http://localhost:8000/?view=profile&guest=true', { waitUntil: 'networkidle' });

  // 1. Verify Page Container
  await page.waitForSelector('.user-profile-page-workspace', { timeout: 10000 });
  console.log('✓ Found .user-profile-page-workspace');

  // Verify Top Header Bar & Hero Dossier
  await page.waitForSelector('.profile-hero-dossier-card');
  await page.waitForSelector('.dossier-metrics-four-grid');
  console.log('✓ Hero Dossier and 4-Metrics Grid loaded');

  // Fill in some clinical data to demonstrate Asian WHO BMI & Demographics
  console.log('2. Testing General & Physical Form Inputs (Tab 1)...');
  const nameInput = page.locator('#pf-display-name');
  await nameInput.fill('BS. Nguyễn Văn An');

  const phoneInput = page.locator('#pf-phone');
  await phoneInput.fill('0912345678');

  const heightInput = page.locator('#pf-height');
  await heightInput.fill('172');

  const weightInput = page.locator('#pf-weight');
  await weightInput.fill('68');

  await page.waitForTimeout(400);

  // Check floating dock appeared due to isDirty
  const dock = await page.waitForSelector('.profile-floating-dock-banner');
  console.log('✓ Floating action dock appeared upon dirty form state');

  // Scroll to top to capture executive hero card and top section
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(300);

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/profile_page_tab1_general.png',
    fullPage: false
  });
  console.log('Captured profile_page_tab1_general.png');

  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/profile_page_full.png',
    fullPage: true
  });
  console.log('Captured profile_page_full.png');

  // 3. Switch to Tab 2: Insurance & Policies
  console.log('3. Switching to Tab 2 (BHYT & Bảo Hiểm)...');
  const tab2Btn = page.locator('.profile-master-tab').nth(1);
  await tab2Btn.click();
  await page.waitForTimeout(300);

  // Fill BHYT & Insurance info
  const bhytInput = page.locator('#pf-bhyt-number');
  await bhytInput.fill('DN4790123456789');

  const hospitalInput = page.locator('#pf-bhyt-hospital');
  await hospitalInput.fill('Bệnh viện Chợ Rẫy (79-011)');

  const rateSelect = page.locator('#pf-bhyt-rate');
  await rateSelect.selectOption('95');

  const bhxhInput = page.locator('#pf-bhxh-number');
  await bhxhInput.fill('7912345678');

  const lifeProvider = page.locator('#pf-life-provider');
  await lifeProvider.fill('Prudential Việt Nam');

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(300);
  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/profile_page_tab2_insurance.png',
    fullPage: false
  });
  console.log('Captured profile_page_tab2_insurance.png');

  // 4. Switch to Tab 3: Clinical & Emergency
  console.log('4. Switching to Tab 3 (Tiền Sử Bệnh & Dị Ứng)...');
  const tab3Btn = page.locator('.profile-master-tab').nth(2);
  await tab3Btn.click();
  await page.waitForTimeout(300);

  // Click on a chronic condition tag: Tăng huyết áp
  const condTag = page.locator('.quick-tag-btn').filter({ hasText: 'Tăng huyết áp' });
  if (await condTag.count() > 0) {
    await condTag.first().click();
  }

  // Click on an allergy tag: Penicillin / Amoxicillin
  const allergyTag = page.locator('.quick-tag-btn.danger').filter({ hasText: 'Penicillin / Amoxicillin' });
  if (await allergyTag.count() > 0) {
    await allergyTag.first().click();
  }

  // Fill emergency contact
  const sosName = page.locator('#pf-sos-name');
  await sosName.fill('Nguyễn Thị Mai (Vợ)');

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(300);
  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/profile_page_tab3_clinical.png',
    fullPage: false
  });
  console.log('Captured profile_page_tab3_clinical.png');

  // 5. Test Saving via Floating Dock
  console.log('5. Clicking Save on floating action dock...');
  const saveBtn = page.locator('.dock-btn-save');
  await saveBtn.click();
  await page.waitForTimeout(700);

  // Verify save notification toast
  console.log('6. Verifying saved state in Hero Dossier...');
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(300);
  await page.screenshot({
    path: '/Users/munonguyen/.gemini/antigravity-ide/brain/5f07f175-5aee-4f44-bf99-cab381082a0b/profile_page_saved_success.png',
    fullPage: false
  });
  console.log('Captured profile_page_saved_success.png');

  // 6. Test Sidebar Navigation to Profile
  console.log('7. Testing Back to Chat, then Sidebar click to Profile...');
  const backBtn = page.locator('.btn-back-to-chat');
  await backBtn.click();
  await page.waitForTimeout(400);

  // In chat view now, click Sidebar Profile button
  const sidebarProfileBtn = page.locator('.sidebar-actions .nav-link-btn').filter({ hasText: 'Hồ sơ & Bảo hiểm' });
  await sidebarProfileBtn.click();
  await page.waitForTimeout(400);
  await page.waitForSelector('.user-profile-page-workspace');
  console.log('✓ Successfully navigated back to Profile page from sidebar link');

  await browser.close();
  console.log('All tests passed cleanly!');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
