import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifactDir = new URL('../../.artifacts/', import.meta.url);
await mkdir(artifactDir, { recursive: true });

async function run() {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  try {
    console.log('Navigating to MedGuard AI...');
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await page.getByText('MedGuard AI').first().waitFor();

    // 1. Open Schedule Page
    console.log('Opening Schedule Page...');
    await page.getByRole('button', { name: 'Lịch ca trực' }).click();
    await page.getByRole('heading', { name: 'Lịch Khám & Ca Trực Lâm Sàng' }).waitFor();

    // 2. Verify Weekly Timetable Grid
    console.log('Verifying Weekly Timetable Grid...');
    await page.getByText('THỜI KHÓA BIỂU DẠNG TUẦN').waitFor();
    await page.getByText('Thứ 2').first().waitFor();
    await page.getByText('Thứ 7').first().waitFor();
    await page.getByText('Chủ Nhật').first().waitFor();
    await page.getByText('Ca Sáng').first().waitFor();
    await page.getByText('Ca Chiều').first().waitFor();

    // 3. Test Hover Popover
    console.log('Testing Hover Popover...');
    const eventCard = page.locator('.timetable-event-card.clinical').first();
    await eventCard.scrollIntoViewIfNeeded();
    await eventCard.hover();
    await page.locator('.shift-hover-popover').waitFor({ state: 'visible', timeout: 3000 });
    await page.locator('.shift-hover-popover .popover-patient-name').waitFor();
    console.log('Hover popover verified with patient details!');

    // Capture screenshot of Timetable with Hover Popover
    await page.waitForTimeout(300);
    await page.screenshot({ path: fileURLToPath(new URL('ui-schedule-timetable.png', artifactDir)), fullPage: false });
    console.log('Captured ui-schedule-timetable.png');

    // 4. Test CRUD: Create new shift
    console.log('Testing Create Shift...');
    await page.getByRole('button', { name: 'Thêm Ca Khám Mới' }).click();
    await page.getByRole('heading', { name: 'Thêm Ca Khám Lâm Sàng Mới' }).waitFor();
    await page.locator('input[name="patientName"]').fill('Lê Hải Nam CRUD');
    await page.locator('input[name="patientRef"]').fill('BN-CRUD-999');
    await page.locator('textarea[name="purpose"]').fill('Khám kiểm tra tổng quát định kỳ và xét nghiệm men gan.');
    await page.getByRole('button', { name: 'Tạo ca khám' }).click();
    await page.getByRole('heading', { name: 'Thêm Ca Khám Lâm Sàng Mới' }).waitFor({ state: 'hidden' });
    await page.getByText('Lê Hải Nam CRUD').first().waitFor();
    console.log('Create Shift verified successfully!');

    // 5. Switch to Medication View & Test User Meds CRUD
    console.log('Testing User Medication View & CRUD...');
    await page.getByRole('button', { name: 'Ca uống thuốc', exact: true }).click();
    await page.getByRole('heading', { name: 'Lịch Ca Uống Thuốc Trong Ngày' }).waitFor();

    // Check-in / Toggle taken
    const firstCheckIn = page.locator('.btn-taken').first();
    await firstCheckIn.click();
    await page.locator('.btn-taken.active').first().waitFor();
    console.log('Medication check-in verified!');

    // Add new user medication
    console.log('Adding new medication reminder...');
    await page.getByRole('button', { name: 'Thêm Thuốc Mới Vào Lịch' }).click();
    await page.getByRole('heading', { name: 'Thêm Lịch Uống Thuốc Cho Bệnh Nhân' }).waitFor();
    await page.locator('input[name="name"]').fill('Panadol Extra Đỏ');
    await page.locator('input[name="strength"]').fill('500mg/65mg');
    await page.locator('input[name="dosage"]').fill('1 viên');
    await page.locator('input[name="instruction"]').fill('Uống khi đau đầu sau bữa ăn');
    await page.locator('input[name="note"]').fill('Dùng tối đa 2 lần/ngày khi cần');
    await page.getByRole('button', { name: 'Lưu lịch uống thuốc' }).click();
    await page.getByRole('heading', { name: 'Thêm Lịch Uống Thuốc Cho Bệnh Nhân' }).waitFor({ state: 'hidden' });
    await page.getByText('Panadol Extra Đỏ').first().waitFor();
    console.log('Add Medication verified successfully!');

    // Capture screenshot of User Medication View
    await page.screenshot({ path: fileURLToPath(new URL('ui-schedule-medication.png', artifactDir)), fullPage: false });
    console.log('Captured ui-schedule-medication.png');

    console.log('ALL SCHEDULE & MEDICATION CRUD TESTS PASSED SUCCESSFULLY!');
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
