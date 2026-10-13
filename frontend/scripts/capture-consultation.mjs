import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const ARTIFACT_DIR = '/Users/munonguyen/.gemini/antigravity-ide/brain/9f158647-933b-4611-b891-c0aacb9df8cf';
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function run() {
  await mkdir(ARTIFACT_DIR, { recursive: true });
  console.log('[BROWSER] Khởi động Chrome không đầu...');
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

  // Đảm bảo chọn BS. Minh Tuấn
  await page.getByRole('button', { name: 'BS. Minh Tuấn', exact: true }).click();
  await page.waitForTimeout(1000);

  const testCases = [
    {
      id: 'consult-explain',
      title: 'Giải thích cơ chế bệnh học',
      text: 'Cơ chế của viêm tủy răng là do vi khuẩn xâm nhập sâu qua men răng và ngà răng.'
    },
    {
      id: 'consult-caution',
      title: 'Cảnh báo lâm sàng & Chống chỉ định',
      text: 'Bạn tuyệt đối không được tự ý tăng liều kháng sinh khi chưa có chỉ định.'
    },
    {
      id: 'consult-guide',
      title: 'Hướng dẫn chăm sóc từng bước',
      text: 'Bạn nên súc miệng bằng nước muối sinh lý ấm và chườm lạnh vùng má 15 phút.'
    },
    {
      id: 'consult-reassure',
      title: 'Đồng cảm & Trấn an tinh thần',
      text: 'Bạn hoàn toàn yên tâm nhé, cảm giác ê buốt này sẽ giảm rõ rệt sau 24 giờ.'
    },
    {
      id: 'consult-compare',
      title: 'So sánh đối chiếu phương án điều trị',
      text: 'Hai phương pháp điều trị này có sự khác nhau về thời gian phục hồi và chi phí.'
    }
  ];

  for (const tc of testCases) {
    console.log(`\n[TESTING] ${tc.title}: "${tc.text}"`);
    await page.evaluate((text) => {
      const e = window.__companionEngine;
      e.setCameraPreset('waist');
      e.motion?.startUtterance(text);
      e.startSpeaking();
    }, tc.text);

    // Chờ 1.6 giây để động tác vươn tới đỉnh điểm (peak stroke)
    await page.waitForTimeout(1600);
    const savePath = path.join(ARTIFACT_DIR, `${tc.id}.png`);
    await page.screenshot({ path: savePath });
    console.log(`[CAPTURED] ${savePath}`);

    await page.evaluate(() => {
      window.__companionEngine?.stopSpeaking();
      window.__companionEngine?.applyPose('pose_idle');
    });
    await page.waitForTimeout(600);
  }

  await browser.close();
  console.log('\n[SUCCESS] Hoàn tất chụp ảnh nghiệm thu các cử chỉ tư vấn lâm sàng!');
}

run().catch(err => {
  console.error('[ERROR]', err);
  process.exit(1);
});
