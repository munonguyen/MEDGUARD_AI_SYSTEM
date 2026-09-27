import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.setDefaultTimeout(12000);

const errors = [];
let lastChatPayload = null;
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
page.on('console', (message) => {
  if (message.type() === 'error') errors.push(`console: ${message.text()}`);
});
page.on('response', async (response) => {
  if (!response.url().endsWith('/v1/chat') || response.request().method() !== 'POST') return;
  try {
    lastChatPayload = await response.json();
  } catch {
    // Ignore non-JSON network noise; the UI assertions below remain authoritative.
  }
});

async function sendMessage(composer, send, text) {
  lastChatPayload = null;
  await composer.fill(text);
  await send.click();
  await page.getByText('MedGuard đang xử lý', { exact: true }).waitFor({ state: 'hidden' });
  if (!lastChatPayload) throw new Error(`No /v1/chat payload captured for: ${text}`);
  return lastChatPayload;
}

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.getByText('MedGuard AI', { exact: true }).first().waitFor();

  const composer = page.getByRole('textbox', { name: 'Tin nhắn' });
  const send = page.getByRole('button', { name: 'Gửi tin nhắn' });

  // 1) EMERGENCY: action first and zero patient-facing clarification questions.
  const emergencyPayload = await sendMessage(
    composer,
    send,
    'Tôi đau ngực dữ dội, khó thở và vã mồ hôi.',
  );
  await page.getByText('Bạn cần được đánh giá cấp cứu ngay', { exact: true }).waitFor();
  if (emergencyPayload?.result?.urgency !== 'EMERGENCY') {
    throw new Error(`Expected EMERGENCY, got ${emergencyPayload?.result?.urgency}`);
  }
  if (!Array.isArray(emergencyPayload?.answer?.display_questions) || emergencyPayload.answer.display_questions.length !== 0) {
    throw new Error(`Emergency policy did not return display_questions=[]: ${JSON.stringify(emergencyPayload?.answer?.display_questions)}`);
  }
  const emergencyAnswer = page.locator('.chat-assistant:not(.pending)').last();
  if (await emergencyAnswer.getByText('Bạn cho mình biết thêm', { exact: true }).count()) {
    throw new Error('Emergency response rendered a clarification section');
  }

  // 2) Natural episode switch after emergency: routine GI answer asks at most one
  // high-information question on the patient surface.
  const routinePayload = await sendMessage(
    composer,
    send,
    'Tôi thấy bụng cứ cồn cào, sốt ruột không rõ lắm.',
  );
  await page.getByText(/chưa đủ để xác định nguyên nhân/).waitFor();
  if (routinePayload?.intent !== 'triage') {
    throw new Error(`Routine GI turn was routed to ${routinePayload?.intent}`);
  }
  const routineDisplay = routinePayload?.answer?.display_questions;
  if (!Array.isArray(routineDisplay) || routineDisplay.length > 1) {
    throw new Error(`Routine display question contract violated: ${JSON.stringify(routineDisplay)}`);
  }
  const routineAnswer = page.locator('.chat-assistant:not(.pending)').last();
  const routineQuestionSection = routineAnswer.locator('.answer-section').filter({
    has: routineAnswer.getByText('Bạn cho mình biết thêm', { exact: true }),
  });
  if (routineDisplay.length && await routineQuestionSection.locator('li').count() !== routineDisplay.length) {
    throw new Error('Routine UI question count differs from backend display_questions');
  }

  // 3) Once nausea is explicitly reported, disposition-changing vomiting /
  // hydration status outranks the older semantic ambiguity question.
  const nauseaPayload = await sendMessage(
    composer,
    send,
    'Cảm giác nó cứ khó chịu, buồn nôn lắm.',
  );
  const nauseaDisplay = nauseaPayload?.answer?.display_questions;
  if (!Array.isArray(nauseaDisplay)) {
    throw new Error(`Nausea payload has no question plan: ${JSON.stringify(nauseaPayload)}`);
  }
  const backendQuestionText = nauseaDisplay.join(' ').toLowerCase();
  if (!backendQuestionText.includes('nôn') || !backendQuestionText.includes('nước')) {
    throw new Error(
      `Backend nausea plan did not prioritize vomiting/hydration. intent=${nauseaPayload?.intent} urgency=${nauseaPayload?.result?.urgency} display=${JSON.stringify(nauseaDisplay)} full=${JSON.stringify(nauseaPayload?.answer?.questions)}`,
    );
  }

  const nauseaAnswer = page.locator('.chat-assistant:not(.pending)').last();
  const nauseaQuestionSection = nauseaAnswer.locator('.answer-section').filter({
    has: nauseaAnswer.getByText('Bạn cho mình biết thêm', { exact: true }),
  });
  const sectionCount = await nauseaQuestionSection.count();
  if (sectionCount !== 1) {
    throw new Error(
      `Backend selected a nausea question but UI rendered ${sectionCount} question sections. display=${JSON.stringify(nauseaDisplay)} dom=${JSON.stringify(await nauseaAnswer.innerText())}`,
    );
  }
  const questionText = (await nauseaQuestionSection.innerText()).toLowerCase();
  if (!questionText.includes('nôn') || !questionText.includes('nước')) {
    throw new Error(`Nausea UI did not render vomiting/hydration: ${questionText}`);
  }

  if (errors.length) throw new Error(errors.join('\n'));
  console.log('dialogue_policy_ui=PASS');
} finally {
  await browser.close();
}
