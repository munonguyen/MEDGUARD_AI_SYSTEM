import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const ARTIFACT_DIR = '/Users/munonguyen/.gemini/antigravity-ide/brain/9f158647-933b-4611-b891-c0aacb9df8cf';
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function capture() {
  await mkdir(ARTIFACT_DIR, { recursive: true });
  console.log('[BROWSER] Khởi động Chrome không đầu (Headless)...');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu-rasterization']
  });

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('[NAVIGATE] Kết nối tới http://127.0.0.1:8000/?view=companion ...');
  await page.goto('http://127.0.0.1:8000/?view=companion');
  await page.waitForFunction(() => window.__companionEngine?.isVrmLoaded, { timeout: 20000 });

  const personas = [
    { id: 'dr_tuan', name: 'BS. Minh Tuấn' },
    { id: 'dr_mai', name: 'BS. Thanh Mai' }
  ];

  for (const p of personas) {
    console.log(`\n--- KIỂM TRA & CHỤP ẢNH XÁC THỰC CHO: ${p.name} ---`);
    if (p.id === 'dr_mai') {
      await page.getByRole('button', { name: 'BS. Thanh Mai', exact: true }).click();
      await page.waitForFunction(() =>
        window.__companionEngine?.isVrmLoaded && window.__companionEngine?.options?.persona === 'dr_mai',
        { timeout: 15000 }
      );
    } else {
      await page.getByRole('button', { name: 'BS. Minh Tuấn', exact: true }).click();
      await page.waitForFunction(() =>
        window.__companionEngine?.isVrmLoaded && window.__companionEngine?.options?.persona === 'dr_tuan',
        { timeout: 15000 }
      );
    }
    await page.waitForTimeout(1000);

    // 1. Chụp tư thế Nghỉ Tự Nhiên (Idle)
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.setCameraPreset('waist');
      e.applyPose('pose_idle');
      e.stopSpeaking();
    });
    await page.waitForTimeout(1200);
    const idlePath = path.join(ARTIFACT_DIR, `trained-${p.id}-idle.png`);
    await page.screenshot({ path: idlePath });
    console.log(`[CAPTURED] Tư thế Idle: ${idlePath}`);

    // 2. Chụp tư thế Chào Hỏi (Greeting)
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.applyPose('pose_wave');
      e.motion?.startUtterance('Xin chào bạn. Tôi là bác sĩ đồng hành MedGuard AI.');
    });
    await page.waitForTimeout(1400); // Bắt khoảnh khắc giữa nhịp chào
    const greetingPath = path.join(ARTIFACT_DIR, `trained-${p.id}-greeting.png`);
    await page.screenshot({ path: greetingPath });
    console.log(`[CAPTURED] Tư thế Greeting: ${greetingPath}`);

    // 3. Chụp tư thế Suy Nghĩ (Thinking)
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.applyPose('pose_thinking');
      e.stopSpeaking();
    });
    await page.waitForTimeout(1200);
    const thinkPath = path.join(ARTIFACT_DIR, `trained-${p.id}-thinking.png`);
    await page.screenshot({ path: thinkPath });
    console.log(`[CAPTURED] Tư thế Thinking: ${thinkPath}`);

    // 4. Chụp tư thế Cúi đầu chào lịch sự (Polite Bow)
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.applyPose('pose_bow');
      e.stopSpeaking();
    });
    await page.waitForTimeout(1400);
    const bowPath = path.join(ARTIFACT_DIR, `trained-${p.id}-bow.png`);
    await page.screenshot({ path: bowPath });
    console.log(`[CAPTURED] Tư thế Bow: ${bowPath}`);

    // 5. Chụp tư thế Ghi chép bệnh án (Note Taking)
    await page.evaluate(() => {
      const e = window.__companionEngine;
      e.applyPose('pose_note_taking');
      e.stopSpeaking();
    });
    await page.waitForTimeout(1400);
    const notePath = path.join(ARTIFACT_DIR, `trained-${p.id}-notes.png`);
    await page.screenshot({ path: notePath });
    console.log(`[CAPTURED] Tư thế Note Taking: ${notePath}`);
  }

  await browser.close();
  console.log('\n[SUCCESS] Đã hoàn tất chụp ảnh nghiệm thu toàn bộ tư thế đã huấn luyện!');
}

capture().catch(err => {
  console.error('[ERROR]', err);
  process.exit(1);
});
