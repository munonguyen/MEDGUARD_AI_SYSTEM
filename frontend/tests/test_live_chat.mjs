import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const targetUrl = 'https://medguard.bookingcare.shop';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

console.log('Testing Live Chat Flow on CloudFront...');
const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage']
});

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });

  // 1. Enter as Guest
  const guestBtn = page.getByRole('button', { name: /Trải nghiệm ngay không cần đăng nhập/i });
  await guestBtn.click();
  await page.waitForTimeout(2000);

  // 2. Click quick prompt
  console.log('Clicking quick clinical prompt...');
  const promptCard = page.locator('text=Tôi bị đau ngực và khó thở');
  if (await promptCard.count() > 0) {
    await promptCard.click();
    await page.waitForTimeout(500);
  }

  // 3. Send message by clicking send button or pressing Enter
  console.log('Sending chat query...');
  const textarea = page.locator('textarea, input[placeholder*="Nhắn cho MedGuard"]');
  await textarea.press('Enter');
  
  // Also try clicking the green send button if still in textarea
  const sendBtn = page.locator('button[type="submit"], .chat-send-btn, button:has(svg.lucide-send)').last();
  if (await sendBtn.count() > 0) {
    await sendBtn.click().catch(() => {});
  }

  // 4. Wait for AI response message
  console.log('Waiting for AI response in chat stream...');
  await page.waitForTimeout(8000);

  await page.screenshot({ path: 'scratch/screenshots/live_chat_response.png' });
  console.log('Saved: scratch/screenshots/live_chat_response.png');

  console.log('Live chat test completed!');
} finally {
  await browser.close();
}
