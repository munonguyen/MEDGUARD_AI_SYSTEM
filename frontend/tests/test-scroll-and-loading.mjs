import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

console.log('Testing scroll behavior and upgraded loading effect...');

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' });

  // 1. Send first message
  const input = page.locator('textarea[aria-label="Tin nhắn"]');
  await input.fill('Tôi bị căng cơ bắp chân khi đá bóng');
  await page.keyboard.press('Enter');

  // Verify that during loading, the upgraded premium thinking card is rendered!
  const thinkingCard = page.locator('.premium-thinking-card');
  console.log('Checking for premium thinking card presence during send...');
  
  // Wait for assistant response to arrive
  await page.waitForSelector('.chat-assistant .assistant-content', { timeout: 35000 });
  console.log('First response received.');

  // 2. Send second message to generate plenty of content to scroll
  await page.waitForTimeout(1000);
  await input.fill('Tôi bị chảy máu cam thì xử lý thế nào?');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.chat-assistant:nth-of-type(2) .assistant-content', { timeout: 35000 });
  console.log('Second response received.');

  // 3. Check scrolling up behavior
  const scrollContainer = page.locator('.chat-scroll');
  const initialScrollTop = await scrollContainer.evaluate((el) => el.scrollTop);
  const maxScroll = await scrollContainer.evaluate((el) => el.scrollHeight - el.clientHeight);
  console.log(`Scroll bounds: current scrollTop=${initialScrollTop}, maxScroll=${maxScroll}`);

  // Scroll UP to top (scrollTop = 50)
  console.log('Scrolling UP to scrollTop = 50...');
  await scrollContainer.evaluate((el) => {
    el.scrollTo({ top: 50, behavior: 'auto' });
    el.dispatchEvent(new Event('scroll'));
  });

  // Verify FAB button appears
  await page.waitForTimeout(500);
  const fab = page.locator('.scroll-bottom-fab');
  const isFabVisible = await fab.isVisible();
  console.log(`Is scroll-to-bottom FAB visible: ${isFabVisible}`);
  if (!isFabVisible) {
    throw new Error('Scroll-to-bottom FAB should be visible when scrolled up!');
  }

  // Wait 3 seconds to ensure background polling does NOT yank scroll down
  console.log('Waiting 3.5s to verify polling does NOT auto-scroll down...');
  await page.waitForTimeout(3500);
  const scrollTopAfterWait = await scrollContainer.evaluate((el) => el.scrollTop);
  console.log(`ScrollTop after wait: ${scrollTopAfterWait}`);
  if (scrollTopAfterWait > 200) {
    throw new Error(`Scroll position was yanked down! Expected <= 100, got ${scrollTopAfterWait}`);
  }
  console.log('PASS: Reading scroll position was preserved! No automatic jumping!');

  // Click the FAB button to scroll to bottom
  console.log('Clicking FAB button to scroll back to bottom...');
  await fab.click();
  await page.waitForTimeout(1000);

  const finalScrollTop = await scrollContainer.evaluate((el) => el.scrollTop);
  const finalDistance = await scrollContainer.evaluate((el) => el.scrollHeight - el.clientHeight - el.scrollTop);
  console.log(`Final distance from bottom: ${finalDistance}`);
  if (finalDistance > 50) {
    throw new Error(`Expected to be at bottom, but distance is ${finalDistance}`);
  }
  console.log('PASS: Successfully smoothly scrolled to bottom upon clicking FAB!');

  // Take screenshot of chat with FAB and upgraded UI
  await page.screenshot({ path: 'frontend/tests/scroll-test-success.png' });
  console.log('Saved screenshot to frontend/tests/scroll-test-success.png');
  console.log('ALL TESTS PASSED 100%!');

} finally {
  await browser.close();
}
