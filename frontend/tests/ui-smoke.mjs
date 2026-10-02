import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifactDir = new URL('../../.artifacts/', import.meta.url);
await mkdir(artifactDir, { recursive: true });

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const errors = [];

async function assertNoHorizontalOverflow(page, viewport) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (dimensions.scrollWidth > dimensions.clientWidth + 1) {
    throw new Error(`${viewport} horizontal overflow: ${JSON.stringify(dimensions)}`);
  }
}

async function assertComposerInsideViewport(page, viewport) {
  const box = await page.locator('.composer-box').boundingBox();
  const size = page.viewportSize();
  if (!box || box.x < 0 || box.y < 0 || box.x + box.width > size.width + 1 || box.y + box.height > size.height + 1) {
    throw new Error(`${viewport} composer outside viewport: ${JSON.stringify(box)}`);
  }
}

async function assertTopbarInsideViewport(page, viewport) {
  const box = await page.locator('.chat-topbar').boundingBox();
  const size = page.viewportSize();
  if (!box || box.x < -1 || box.y < -1 || box.x + box.width > size.width + 1 || box.y + box.height > size.height + 1) {
    throw new Error(`${viewport} topbar outside viewport: ${JSON.stringify(box)}`);
  }
}

function captureErrors(page, viewport) {
  page.on('pageerror', (error) => errors.push(`${viewport} pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`${viewport} console: ${message.text()}`);
  });
}

try {
  const schedulePatient = `BN-UI-${Date.now()}`;
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  desktop.setDefaultTimeout(10000);
  captureErrors(desktop, 'desktop');
  await desktop.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await desktop.getByText('MedGuard AI', { exact: true }).first().waitFor();
  await desktop.getByRole('heading', { name: 'Bạn cần hỗ trợ gì hôm nay?' }).waitFor();

  await desktop.getByRole('button', { name: 'Mở Profile cá nhân' }).click();
  await desktop.getByLabel('Tên hiển thị').fill('An UI');
  await desktop.getByLabel('Tuổi', { exact: true }).fill('36');
  await desktop.getByLabel('Giới tính').selectOption('male');
  await desktop.getByLabel('Mã hồ sơ').fill(schedulePatient);
  await desktop.getByLabel('Thuốc đang dùng').fill('warfarin');
  await desktop.getByLabel('Bệnh nền').fill('tăng huyết áp');
  await desktop.getByRole('button', { name: 'Lưu Profile' }).click();
  await desktop.getByText('An UI', { exact: true }).waitFor();
  await desktop.reload({ waitUntil: 'domcontentloaded' });
  await desktop.getByText('An UI', { exact: true }).waitFor();

  await desktop.getByRole('button', { name: 'Mở Profile cá nhân' }).click();
  await desktop.getByText('Thông tin không bắt buộc').waitFor();
  await desktop.keyboard.press('Escape');
  await desktop.getByText('Thông tin không bắt buộc').waitFor({ state: 'hidden' });

  await desktop.getByRole('button', { name: 'Thu gọn thanh bên' }).click();
  await desktop.getByRole('button', { name: 'Mở thanh bên' }).waitFor();
  await desktop.waitForFunction(() => document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1);
  await desktop.getByRole('button', { name: 'Mở thanh bên' }).click();
  await desktop.getByRole('button', { name: 'Thu gọn thanh bên' }).waitFor();
  await desktop.waitForFunction(() => document.querySelector('.sidebar')?.getBoundingClientRect().left >= -1);

  await desktop.getByRole('button', { name: 'Tôi bị đau ngực và khó thở' }).click();
  await desktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await desktop.getByText('MedGuard đang xử lý', { exact: true }).waitFor();
  if (await desktop.getByText('Bạn cần được đánh giá cấp cứu ngay', { exact: true }).count()) {
    throw new Error('The final answer must remain hidden while MedGuard is processing');
  }
  await desktop.screenshot({ path: fileURLToPath(new URL('ui-processing-desktop.png', artifactDir)), fullPage: false });
  await desktop.getByRole('heading', { name: 'Bạn cần được đánh giá cấp cứu ngay', exact: true }).waitFor();
  await desktop.getByText('MedGuard đang xử lý', { exact: true }).waitFor({ state: 'hidden' });
  const emergencyAnswer = desktop.locator('.chat-assistant:not(.pending):visible').last();
  await emergencyAnswer.locator('.answer-narrative .urgent:visible').waitFor();
  if (await desktop.getByText(/Cơ sở trả lời|Chi tiết dữ liệu nghiệp vụ/).count()) {
    throw new Error('Internal answer details must not be visible in chat');
  }
  await emergencyAnswer.hover();
  await emergencyAnswer.getByRole('button', { name: 'Sao chép phản hồi' }).click();
  await emergencyAnswer.getByRole('button', { name: 'Đã sao chép' }).waitFor();
  await desktop.getByRole('status').filter({ hasText: 'Đã sao chép phản hồi' }).waitFor();

  const composer = desktop.getByRole('textbox', { name: 'Tin nhắn' });
  await composer.fill('Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm.');
  await desktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await desktop.getByText(/chưa đủ để xác định nguyên nhân/).waitFor();
  const abdominalAnswer = desktop.locator('.chat-assistant:not(.pending)').last();
  if (await abdominalAnswer.locator('.triage-status-pill').count()) {
    throw new Error('Routine guidance must render as conversational prose without a status badge');
  }
  await abdominalAnswer.getByText(/Khi nói “sốt ruột”/).waitFor();
  if (await abdominalAnswer.getByText(/Gateway|Nguồn chưa ghi nhận phê duyệt|Nguồn đang chờ chuyên gia duyệt/).count()) {
    throw new Error('Internal gateway/knowledge governance metadata must not render in patient chat');
  }
  if (await abdominalAnswer.getByText(/Điều phối tiếp theo|Thêm dấu hiệu sinh tồn|Xuất FHIR/).count()) {
    throw new Error('Automatic workflow shortcuts must not interrupt the conversational answer');
  }

  await composer.fill('Cảm giác nó cứ khó chịu, buồn nôn lắm.');
  await desktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await desktop.getByText('MedGuard đang xử lý', { exact: true }).waitFor({ state: 'hidden' });
  const abdominalFollowUp = desktop.locator('.chat-assistant:not(.pending)').last();
  await abdominalFollowUp.getByText(/bụng cồn cào/).first().waitFor();
  await abdominalFollowUp.getByText(/Bạn đã mô tả buồn nôn/).waitFor();
  await abdominalFollowUp.screenshot({ path: fileURLToPath(new URL('ui-abdominal-followup.png', artifactDir)) });

  await desktop.getByRole('button', { name: 'Tự nhận diện' }).click();
  await desktop.getByRole('menu').waitFor();
  await desktop.keyboard.press('Escape');
  await desktop.getByRole('menu').waitFor({ state: 'hidden' });
  await composer.fill('#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày.');
  await desktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await desktop.getByText(/Đã thêm 2 mốc uống amoxicillin/).waitFor();

  // Verify dedicated Medication Page
  await desktop.locator('.sidebar-actions').getByRole('button', { name: 'Lịch uống thuốc' }).click();
  await desktop.getByRole('heading', { name: 'Lịch Uống Thuốc', exact: true }).waitFor();
  await desktop.getByText('Tuân thủ tuần này').waitFor();
  await desktop.getByRole('button', { name: 'Về phòng Chat' }).click();
  await desktop.getByRole('textbox', { name: 'Tin nhắn' }).waitFor();

  await desktop.getByRole('button', { name: 'Quét QR' }).click();
  await desktop.getByRole('button', { name: 'Nhập mã' }).click();
  await desktop.getByPlaceholder('MEDGUARD|product=...|serial=...|lot=...').fill('MEDGUARD|product=MG-AMOX-500|serial=VN24A001|lot=AMX2409');
  await desktop.getByRole('button', { name: 'Kiểm tra mã' }).click();
  await desktop.getByText('Mã khớp với registry hiện tại', { exact: true }).waitFor();
  await desktop.getByText('Kết quả phản ánh việc đối chiếu dữ liệu trong mã với registry đang kết nối, không phải kiểm định vật lý sản phẩm.').waitFor();

  await assertNoHorizontalOverflow(desktop, 'desktop');
  await assertComposerInsideViewport(desktop, 'desktop');
  await assertTopbarInsideViewport(desktop, 'desktop');
  if (await desktop.getByRole('button', { name: 'Mở menu' }).isVisible()) throw new Error('Desktop menu button must be hidden');

  // Test Dedicated Lịch Khám Page
  await desktop.locator('.topbar-actions').getByRole('button', { name: 'Lịch khám' }).click();
  await desktop.getByRole('heading', { name: 'Lịch Khám', exact: true }).waitFor();
  await desktop.getByText('Tổng Ca Hôm Nay').waitFor();
  await desktop.getByText('Nguyễn Văn An').first().waitFor();
  await desktop.getByRole('button', { name: 'Danh sách ca' }).click();
  await desktop.getByRole('button', { name: 'Thời khóa biểu tuần' }).click();
  await desktop.getByRole('button', { name: 'Về phòng Chat' }).click();
  await desktop.getByRole('textbox', { name: 'Tin nhắn' }).waitFor();
  await desktop.screenshot({ path: fileURLToPath(new URL('ui-chat-desktop.png', artifactDir)), fullPage: false });

  await desktop.getByRole('button', { name: 'Cài đặt' }).first().click();
  await desktop.getByRole('button', { name: 'System & audit' }).click();
  await desktop.getByText('sqlite-memory').waitFor();
  await desktop.getByRole('button', { name: 'Audit', exact: true }).click();
  await desktop.getByText('chat.route').first().waitFor();
  await desktop.getByRole('button', { name: 'Đóng cài đặt' }).click();

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  mobile.setDefaultTimeout(10000);
  captureErrors(mobile, 'mobile');
  await mobile.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await mobile.getByRole('button', { name: 'Mở menu' }).click();
  await mobile.getByRole('button', { name: 'Cuộc trò chuyện mới' }).click();
  await mobile.getByRole('heading', { name: 'Bạn cần hỗ trợ gì hôm nay?' }).waitFor();
  await mobile.getByRole('textbox', { name: 'Tin nhắn' }).fill('Tôi bị đau đầu, sốt và buồn nôn từ sáng nay.');
  await mobile.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await mobile.getByText('Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu', { exact: true }).waitFor();
  await mobile.getByText('Bạn cho mình biết thêm', { exact: true }).waitFor();
  await mobile.getByText('Đi cấp cứu ngay nếu đau đầu xuất hiện đột ngột và rất dữ dội', { exact: true }).waitFor();
  if (await mobile.locator('.answer-narrative p').count() < 4) throw new Error('Expected a four-part conversational headache answer');
  if (await mobile.locator('.answer-narrative strong').count() < 3) throw new Error('Expected bounded emphasis in narrative answer');
  await mobile.waitForTimeout(350);
  await mobile.screenshot({ path: fileURLToPath(new URL('ui-answer-mobile-direct.png', artifactDir)), fullPage: false });
  await mobile.getByRole('button', { name: 'Quét QR' }).click();
  await mobile.getByRole('heading', { name: 'Xác thực sản phẩm' }).waitFor();
  await mobile.getByRole('button', { name: 'Đóng', exact: true }).click();
  await assertNoHorizontalOverflow(mobile, 'mobile');
  await assertComposerInsideViewport(mobile, 'mobile');
  await assertTopbarInsideViewport(mobile, 'mobile');
  await mobile.screenshot({ path: fileURLToPath(new URL('ui-chat-mobile.png', artifactDir)), fullPage: false });

  const answerDesktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  answerDesktop.setDefaultTimeout(10000);
  captureErrors(answerDesktop, 'answer-desktop');
  await answerDesktop.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await answerDesktop.getByRole('textbox', { name: 'Tin nhắn' }).fill('Tôi đang bị đau đầu góc trái đầu.');
  await answerDesktop.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await answerDesktop.getByText('Bạn cho mình biết thêm', { exact: true }).waitFor();
  await assertNoHorizontalOverflow(answerDesktop, 'answer-desktop');
  await assertComposerInsideViewport(answerDesktop, 'answer-desktop');
  await answerDesktop.screenshot({ path: fileURLToPath(new URL('ui-answer-desktop-direct.png', artifactDir)), fullPage: false });

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
    body.answer.narrative = body.answer.narrative.map((block) => ({ ...block, source_ids: ['src_nice'] }));
    body.answer.answer_assurance = {
      status: 'verified',
      scores: { grounding: 0.98, safety: 0.99, completeness: 0.96, clarity: 0.95, citation_coverage: 0.98 },
    };
    await route.fulfill({ response: upstream, json: body });
  });
  await agentUi.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await agentUi.getByRole('textbox', { name: 'Tin nhắn' }).fill('Tôi đang bị đau đầu góc trái đầu.');
  await agentUi.getByRole('button', { name: 'Gửi tin nhắn' }).click();
  await agentUi.getByText('Bạn cho mình biết thêm', { exact: true }).waitFor();
  if (await agentUi.getByText(/Cơ sở trả lời|Chi tiết dữ liệu nghiệp vụ|Đã kiểm chứng thông tin và nguồn tham khảo/).count()) {
    throw new Error('Internal answer metadata must not be visible in chat');
  }
  if (await agentUi.getByText(/Gemini|GPT|Verifier Agent|shadow|deterministic fallback/i).count()) {
    throw new Error('Confidential model-processing details are visible in the UI');
  }
  const researchedSource = agentUi.getByRole('link', { name: /Mở nguồn 1/ }).first();
  await researchedSource.waitFor();
  await researchedSource.evaluate((element) => element.scrollIntoView({ block: 'center' }));
  await agentUi.waitForTimeout(100);
  const sourceBox = await researchedSource.boundingBox();
  const composerBox = await agentUi.locator('.composer-wrap').boundingBox();
  if (!sourceBox || !composerBox || sourceBox.y + sourceBox.height > composerBox.y) {
    throw new Error(`Inline citation is obscured by composer: ${JSON.stringify({ sourceBox, composerBox })}`);
  }
  await assertNoHorizontalOverflow(agentUi, 'agent-ui');
  await assertComposerInsideViewport(agentUi, 'agent-ui');
  await agentUi.screenshot({ path: fileURLToPath(new URL('ui-agent-verification-desktop.png', artifactDir)), fullPage: false });

  if (errors.length) throw new Error(errors.join('\n'));
  console.log('ui_smoke=PASS desktop=1440x1000 mobile=390x844 narrative=PASS agents=PASS schedule=PASS qr=PASS history=PASS audit=PASS');
} finally {
  await browser.close();
}
