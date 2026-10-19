import { chromium } from 'playwright-core';

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function testConversation() {
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-gpu-rasterization']
  });

  const page = await browser.newPage();
  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`[PAGE_ERROR] ${err.message}`));

  console.log('[NAVIGATE] Kết nối tới http://127.0.0.1:8000/?view=companion ...');
  await page.goto('http://127.0.0.1:8000/?view=companion');
  await page.waitForFunction(() => window.__companionEngine?.isVrmLoaded, { timeout: 20000 });

  // 1. Kiểm tra bấm "Đọc lại"
  console.log('[ACTION] Bấm "Đọc lại"...');
  const replayBtn = page.getByRole('button', { name: 'Đọc lại' });
  await replayBtn.click();
  await page.waitForTimeout(1500);

  let state = await page.evaluate(() => ({
    isSpeaking: window.__companionEngine?.isSpeaking,
    hasAnalyser: !!window.__companionEngine?.audioAnalyser,
  }));
  console.log('[STATE after replay]:', state);

  // 2. Gửi câu hỏi qua khung chat
  const query = 'Tôi bị đau họng và sốt nhẹ thì uống thuốc gì?';
  console.log(`[ACTION] Nhập câu hỏi: "${query}"...`);
  const input = page.getByPlaceholder(/Hỏi BS\./i);
  await input.fill(query);
  await input.press('Enter');

  console.log('[WAIT] Đang chờ câu trả lời và giọng đọc từ bác sĩ...');
  // Chờ cho tới khi phân tích xong và câu trả lời thực tế xuất hiện
  await page.waitForFunction(() => {
    const bubble = document.querySelector('.grok-bubble-text')?.textContent || '';
    return !bubble.includes('đang phân tích') && bubble.length > 20;
  }, { timeout: 35000 });

  await page.waitForTimeout(2000);

  const finalState = await page.evaluate(() => {
    const bubble = document.querySelector('.grok-bubble-text')?.textContent;
    const alert = document.querySelector('[role="alert"]')?.textContent;
    return {
      isSpeaking: window.__companionEngine?.isSpeaking,
      dialogue: bubble,
      alertError: alert || null,
      hasAnalyser: !!window.__companionEngine?.audioAnalyser
    };
  });

  console.log('[FINAL CONVERSATION STATE]:', JSON.stringify(finalState, null, 2));
  console.log('[CONSOLE LOGS (filtered)]:');
  consoleLogs.filter(l => !l.includes('PCFSoftShadowMap') && !l.includes('VRMLookAtQuaternionProxy')).forEach(l => console.log('  ', l));

  await browser.close();
}

testConversation().catch(console.error);
