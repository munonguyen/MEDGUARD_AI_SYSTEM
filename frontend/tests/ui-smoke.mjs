import { authenticatePage } from './login-helper.mjs';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifactDir = new URL('../../.artifacts/', import.meta.url);
await mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const errors = [];

function currentAssistant(page) {
  return page.locator('.chat-assistant:not(.pending):visible').last();
}

function captureErrors(page, label) {
  page.on('pageerror', (error) => errors.push(`${label} pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`${label} console: ${message.text()}`);
  });
}

async function assertLayout(page, label) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (dimensions.scrollWidth > dimensions.clientWidth + 1) {
    throw new Error(`${label} horizontal overflow: ${JSON.stringify(dimensions)}`);
  }

  for (const selector of ['.composer-box', '.chat-topbar']) {
    const box = await page.locator(selector).boundingBox();
    const viewport = page.viewportSize();
    if (!box || box.x < -1 || box.y < -1 || box.x + box.width > viewport.width + 1 || box.y + box.height > viewport.height + 1) {
      throw new Error(`${label} ${selector} outside viewport: ${JSON.stringify(box)}`);
    }
  }
}

async function send(page, text) {
  const composer = page.getByRole('textbox', { name: 'Tin nhắn' });
  await composer.fill(text);
  await page.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  const thinking = page.locator('.premium-thinking-card, .chat-assistant.pending, [role="status"]:has-text("MedGuard đang xử lý")');
  try {
    await thinking.waitFor({ state: 'visible', timeout: 2500 });
  } catch {}
  if (await thinking.count()) {
    await thinking.first().waitFor({ state: 'hidden', timeout: 25000 });
  }
  return currentAssistant(page);
}

try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  desktop.setDefaultTimeout(10000);
  captureErrors(desktop, 'desktop');
  await authenticatePage(desktop, baseUrl);
  await desktop.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await desktop.getByRole('heading', { name: 'Bạn cần hỗ trợ gì hôm nay?' }).waitFor();

  const patientRef = `BN-UI-${Date.now()}`;
  await desktop.getByRole('button', { name: 'Mở Profile cá nhân' }).click();
  await desktop.getByLabel('Tên hiển thị').fill('An UI');
  await desktop.getByLabel('Tuổi', { exact: true }).fill('36');
  await desktop.getByLabel('Giới tính').selectOption('male');
  await desktop.getByLabel('Mã hồ sơ').fill(patientRef);
  await desktop.getByLabel('Thuốc đang dùng').fill('warfarin');
  await desktop.getByLabel('Bệnh nền').fill('tăng huyết áp');
  await desktop.getByRole('button', { name: 'Lưu Profile' }).click();
  await desktop.getByText('An UI', { exact: true }).waitFor();
  await desktop.reload({ waitUntil: 'domcontentloaded' });
  await desktop.getByText('An UI', { exact: true }).waitFor();

  await desktop.getByRole('button', { name: 'Thu gọn thanh bên' }).click();
  await desktop.getByRole('button', { name: 'Mở thanh bên' }).waitFor();
  await desktop.getByRole('button', { name: 'Mở thanh bên' }).click();
  await desktop.getByRole('button', { name: 'Thu gọn thanh bên' }).waitFor();

  await desktop.getByRole('button', { name: 'Tôi bị đau ngực và khó thở' }).click();
  await desktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await desktop.getByText('MedGuard đang xử lý', { exact: true }).waitFor();
  if (await desktop.getByRole('heading', { name: 'Gọi 115 hoặc đến khoa Cấp cứu ngay', exact: true }).count()) {
    throw new Error('Final emergency response became visible before processing completed');
  }
  await desktop.screenshot({ path: fileURLToPath(new URL('ui-processing-desktop.png', artifactDir)) });
  await desktop.getByText('MedGuard đang xử lý', { exact: true }).waitFor({ state: 'hidden' });
  const emergency = currentAssistant(desktop);
  await emergency.locator('.clinical-summary-card.status-emergency').waitFor();
  await emergency.getByText('Cấp cứu ngay', { exact: true }).waitFor();
  await emergency.getByText('Hành động và dấu hiệu khẩn cấp', { exact: true }).waitFor();
  if (await emergency.getByText(/Cơ sở trả lời|Chi tiết dữ liệu nghiệp vụ|deterministic fallback/i).count()) {
    throw new Error('Internal processing metadata leaked into emergency response');
  }

  const abdominal = await send(desktop, 'Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm.');
  await abdominal.getByText(/chưa đủ.*xác định/).first().waitFor();
  await abdominal.getByText(/sốt ruột/).first().waitFor();
  const followUp = await send(desktop, 'Cảm giác nó cứ khó chịu, buồn nôn lắm.');
  await followUp.getByText(/cồn cào/).first().waitFor();
  await followUp.getByText(/buồn nôn/).first().waitFor();
  await followUp.screenshot({ path: fileURLToPath(new URL('ui-abdominal-followup.png', artifactDir)) });

  await desktop.getByRole('button', { name: 'Tự nhận diện' }).click();
  await desktop.getByRole('menu').waitFor();
  await desktop.keyboard.press('Escape');
  const schedule = await send(desktop, '#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày.');
  await schedule.getByText(/Đã thêm 2 mốc uống amoxicillin/).first().waitFor();
  await desktop.locator('.sidebar-actions').getByRole('button', { name: 'Lịch uống thuốc' }).click();
  await desktop.getByRole('heading', { name: 'Lịch Uống Thuốc', exact: true }).waitFor();
  await desktop.getByText('Tuân thủ tuần này').waitFor();
  await desktop.getByRole('button', { name: 'Về phòng Chat' }).click();

  await desktop.getByRole('button', { name: 'Quét QR' }).click();
  await desktop.getByRole('button', { name: 'Nhập mã' }).click();
  await desktop.getByPlaceholder('MEDGUARD|product=...|serial=...|lot=...').fill('MEDGUARD|product=MG-AMOX-500|serial=VN24A001|lot=AMX2409');
  await desktop.getByRole('button', { name: 'Kiểm tra mã' }).click();
  await desktop.getByRole('heading', { name: 'Mã khớp với registry hiện tại', exact: true }).waitFor();
  await desktop.getByText(/không (phải kiểm định vật lý|thay thế việc kiểm tra kỹ bao bì vật lý|tự chứng minh bao bì)/).first().waitFor();
  await desktop.keyboard.press('Escape');

  await (desktop.locator('.topbar-actions').getByRole('tab', { name: 'Lịch khám' }).or(desktop.locator('.topbar-actions').getByRole('button', { name: 'Lịch khám' }))).click();
  await desktop.getByRole('heading', { name: 'Lịch Khám', exact: true }).waitFor();
  await desktop.getByText('Tổng Ca Hôm Nay').waitFor();
  await desktop.getByRole('button', { name: 'Danh sách ca' }).click();
  await desktop.getByRole('button', { name: 'Thời khóa biểu tuần' }).click();
  await desktop.getByRole('button', { name: 'Về phòng Chat' }).click();
  await desktop.getByRole('button', { name: 'Cài đặt' }).first().click();
  if (await desktop.getByRole('button', { name: 'System & audit' }).count()) throw new Error('Patient sees administrative settings');
  await desktop.getByRole('button', { name: 'Đóng cài đặt' }).click();
  await assertLayout(desktop, 'desktop');
  await desktop.screenshot({ path: fileURLToPath(new URL('ui-chat-desktop.png', artifactDir)) });

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  mobile.setDefaultTimeout(10000);
  captureErrors(mobile, 'mobile');
  await authenticatePage(mobile, baseUrl);
  await mobile.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await mobile.getByRole('button', { name: 'Mở menu' }).click();
  await mobile.getByRole('button', { name: 'Cuộc trò chuyện mới' }).click();
  const mobileAnswer = await send(mobile, 'Tôi đau đầu nhẹ sau thức khuya, không sốt, không nôn, không yếu liệt.');
  await mobileAnswer.locator('.clinical-summary-card.status-routine').waitFor();
  await mobileAnswer.getByText('Thông tin cần biết thêm', { exact: true }).waitFor();
  await mobileAnswer.getByText('Khi nào cần đi khám / cấp cứu', { exact: true }).waitFor();
  if (await mobileAnswer.getByText('Cấp cứu ngay', { exact: true }).count()) {
    throw new Error('Benign mobile control rendered as active emergency');
  }
  await assertLayout(mobile, 'mobile');
  await mobile.screenshot({ path: fileURLToPath(new URL('ui-answer-mobile-direct.png', artifactDir)) });
  await mobile.getByRole('button', { name: 'Quét QR' }).click();
  await mobile.getByRole('heading', { name: 'Xác thực sản phẩm' }).waitFor();
  await mobile.getByRole('button', { name: 'Đóng', exact: true }).click();

  const agentUi = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  agentUi.setDefaultTimeout(10000);
  captureErrors(agentUi, 'agent-ui');
  await agentUi.route('**/v1/chat', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const upstream = await route.fetch();
    const body = await upstream.json();
    const source = {
      source_id: 'src_nice',
      title: 'Headaches in over 12s: diagnosis and management',
      publisher: 'NICE',
      url: 'https://www.nice.org.uk/guidance/cg150',
      authority_tier: 'guideline_or_regulator',
      supports_claim_ids: ['summary_1'],
    };
    body.answer.researched_sources = [source];
    body.answer.narrative = (body.answer.narrative || []).map((block) => ({ ...block, source_ids: ['src_nice'] }));
    body.answer.answer_assurance = {
      status: 'verified',
      scores: { grounding: 0.98, safety: 0.99, completeness: 0.96, clarity: 0.95, citation_coverage: 0.98 },
    };
    await route.fulfill({ response: upstream, json: body });
  });
  await authenticatePage(agentUi, baseUrl);
  await agentUi.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  const verified = await send(agentUi, 'Tôi đang bị đau đầu góc trái đầu.');
  await verified.getByText('Thông tin cần biết thêm', { exact: true }).waitFor();
  if (await verified.getByText(/Gemini|GPT|Verifier Agent|shadow|deterministic fallback/i).count()) {
    throw new Error('Confidential model-processing details are visible in the UI');
  }
  const detail = verified.getByText('Giải thích chi tiết', { exact: true });
  await detail.waitFor();
  await detail.click();
  const sourceLink = verified.getByRole('link', { name: /Mở nguồn 1/ }).first();
  await sourceLink.waitFor();
  await sourceLink.evaluate((element) => element.scrollIntoView({ block: 'center' }));
  const sourceBox = await sourceLink.boundingBox();
  const composerBox = await agentUi.locator('.composer-wrap').boundingBox();
  if (!sourceBox || !composerBox || sourceBox.y + sourceBox.height > composerBox.y) {
    throw new Error(`Inline citation is obscured by composer: ${JSON.stringify({ sourceBox, composerBox })}`);
  }
  await assertLayout(agentUi, 'agent-ui');
  await agentUi.screenshot({ path: fileURLToPath(new URL('ui-agent-verification-desktop.png', artifactDir)) });

  if (errors.length) throw new Error(errors.join('\n'));
  console.log('ui_smoke=PASS desktop=PASS mobile=PASS emergency=PASS routine=PASS schedule=PASS qr=PASS patient_acl=PASS citations=PASS');
} finally {
  await browser.close();
}
