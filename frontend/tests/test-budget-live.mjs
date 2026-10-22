import assert from 'node:assert/strict';
import { authenticatePage } from './login-helper.mjs';
import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function run() {
  console.log('🚀 Running Live End-to-End Budget & Card Suppression Test...');
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const page = await browser.newPage({ viewport: { width: 1280, height: 850 } });

  try {
    await authenticatePage(page, baseUrl);
    await page.goto(`${baseUrl}/?view=chat`, { waitUntil: 'networkidle', timeout: 15000 });
    console.log('✅ Authenticated & loaded chat view.');

    // 1. Submit budget update to 10 million
    const userText = 'tổng chi tiêu tháng này tôi muốn là tối đa khoảng 10 triệu vào việc mua thuốc và khám sức khoẻ';
    const composer = page.locator('textarea.composer-input, textarea, input.composer-input').first();
    await composer.waitFor({ state: 'visible', timeout: 8000 });
    await composer.fill(userText);
    
    const sendBtn = page.locator('button.composer-submit, button[type="submit"], button.send-button').first();
    if (await sendBtn.isVisible()) {
      await sendBtn.click();
    } else {
      await composer.press('Enter');
    }
    console.log('✅ Sent message to update budget to 10 million.');

    // Wait for assistant response to settle
    const assistantMsg = page.locator('.chat-assistant:not(.pending), .chat-bubble.assistant').last();
    await assistantMsg.waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(2000);

    const msgHtml = await assistantMsg.innerHTML();

    // Check 1: Must show 10.000.000
    assert.ok(msgHtml.includes('10.000.000'), 'Must contain 10.000.000 đ in response');
    console.log('✅ Verified 10.000.000 đ is in the response.');

    // Check 2: Must NOT have Paracetamol / OTC drug prescription card
    assert.ok(!msgHtml.includes('DANH MỤC HOẠT CHẤT OTC AN TOÀN'), 'Must NOT propose OTC medication list');
    assert.ok(!msgHtml.includes('Paracetamol (Acetaminophen) 500mg'), 'Must NOT propose Paracetamol');
    console.log('✅ Verified NO OTC medication proposal card displayed.');

    // Check 3: Must NOT have Leaflet GPS map or route
    assert.ok(!msgHtml.includes('LIVE TRAFFIC RADAR'), 'Must NOT show Leaflet GPS radar');
    assert.ok(!msgHtml.includes('ĐIỂM BÁN THUỐC GPP GẦN NHẤT & CHỈ ĐƯỜNG REAL-TIME'), 'Must NOT show GPS routing');
    console.log('✅ Verified NO map or GPS turn-by-turn routing card displayed.');

    // Check 4: Must NOT have toothache/dental follow-up questions
    assert.ok(!msgHtml.includes('đau răng'), 'Must NOT suggest toothache questions');
    assert.ok(!msgHtml.includes('ê buốt'), 'Must NOT suggest tooth sensitivity questions');
    console.log('✅ Verified NO toothache suggestions displayed.');

    // Check 5: FinancialAdvisoryCard rendered with 3 pillars
    assert.ok(msgHtml.includes('financial-advisory-card') || msgHtml.includes('Khám Chuyên Khoa & BHYT') || msgHtml.includes('Khám chuyên khoa'), 'Must render financial advisory card');
    console.log('✅ Verified FinancialAdvisoryCard rendered cleanly.');

    // Check 6: Navigate to spending dashboard
    console.log('Navigating to spending dashboard...');
    await page.goto(`${baseUrl}/?view=spending`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1500);

    const spendingPageText = await page.locator('body').innerText();
    assert.ok(spendingPageText.includes('10.000.000'), 'Spending dashboard MUST display 10.000.000 đ');
    console.log('✅ Verified Spending Dashboard displays 10.000.000 đ.');

    // Check 7: Reload spending page to verify persistence across page reloads
    console.log('Testing persistence across page reload...');
    await page.reload({ waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1500);
    const reloadedSpendingText = await page.locator('body').innerText();
    assert.ok(reloadedSpendingText.includes('10.000.000'), 'Spending dashboard MUST retain 10.000.000 đ after reload');
    console.log('✅ Verified 10.000.000 đ persists across page reload.');

    console.log('🎉 ALL LIVE CHECKS PASSED PERFECTLY!');
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error('❌ Test failed:', err);
  process.exit(1);
});
