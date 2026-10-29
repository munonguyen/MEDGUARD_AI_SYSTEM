import { chromium } from 'playwright-core';
import path from 'path';

const artifactDir = '/Users/munonguyen/.gemini/antigravity-ide/brain/fb02f5e5-5769-468e-b5f0-5313a7441d04';

const browser = await chromium.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true
});

try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
    geolocation: { latitude: 21.1078, longitude: 105.9561 },
    permissions: ['geolocation']
  });

  const page = await context.newPage();

  console.log('1. Logging in...');
  await page.goto('https://medguard.bookingcare.shop/?view=navigation', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);

  // Check if login form is visible
  const usernameInput = page.locator('#auth-username');
  if (await usernameInput.count() > 0) {
    console.log('Login form detected, filling...');
    await usernameInput.fill('nam1@gmail.com');
    await page.locator('#auth-password').fill('Password123!');
    await page.locator('button[type="submit"]:has-text("Đăng nhập")').click();
    await page.waitForTimeout(4000);
  }

  console.log('Current URL:', page.url());
  const shotCurrent = path.join(artifactDir, 'screenshot_diag_state.png');
  await page.screenshot({ path: shotCurrent });
  console.log('Saved diag screenshot:', shotCurrent);

  // Check buttons on page
  const buttonsText = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).map(b => b.className + ' | ' + b.textContent.trim().slice(0, 30));
  });
  console.log('Buttons on page:', buttonsText);

} catch (err) {
  console.error('Diag error:', err);
} finally {
  await browser.close();
}
