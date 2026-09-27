import { chromium } from 'playwright-core';

const baseUrl = process.env.MEDGUARD_UI_URL || 'http://127.0.0.1:8000';
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const browser = await chromium.launch({ headless: true, executablePath: chromePath });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.setDefaultTimeout(12000);

const errors = [];
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
page.on('console', (message) => {
  if (message.type() === 'error') errors.push(`console: ${message.text()}`);
});

try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
  await page.getByText('MedGuard AI', { exact: true }).first().waitFor();

  const composer = page.getByRole('textbox', { name: 'Tin nhắn' });
  const send = page.getByRole('button', { name: 'Gửi tin nhắn' });

  // 1) EMERGENCY: action first and zero patient-facing clarification questions.
  await composer.fill('Tôi đau ngực dữ dội, khó thở và vã mồ hôi.');
  await send.click();
  await page.getByText('Bạn cần được đánh giá cấp cứu ngay', { exact: true }).waitFor();
  const emergencyAnswer = page.locator('.chat-assistant:not(.pending)').last();
  if (await emergencyAnswer.getByText('Bạn cho mình biết thêm', { exact: true }).count()) {
    throw new Error('Emergency response rendered a clarification section');
  }

  // 2) Natural episode switch after emergency: routine GI answer asks at most one
  // high-information question on the patient surface.
  await composer.fill('Tôi thấy bụng cứ cồn cào, sốt ruột không rõ lắm.');
  await send.click();
  await page.getByText(/chưa đủ để xác định nguyên nhân/).waitFor();
  const routineAnswer = page.locator('.chat-assistant:not(.pending)').last();
  const routineQuestionSection = routineAnswer.locator('.answer-section').filter({
    has: routineAnswer.getByText('Bạn cho mình biết thêm', { exact: true }),
  });
  const routineQuestions = routineQuestionSection.locator('li');
  if (await routineQuestions.count() > 1) {
    throw new Error('Routine response rendered more than one clarification question');
  }

  // 3) Once nausea is explicitly reported, disposition-changing vomiting /
  // hydration status outranks the older semantic ambiguity question.
  await composer.fill('Cảm giác nó cứ khó chịu, buồn nôn lắm.');
  await send.click();
  await page.getByText('MedGuard đang xử lý', { exact: true }).waitFor({ state: 'hidden' });
  const nauseaAnswer = page.locator('.chat-assistant:not(.pending)').last();
  const nauseaQuestionSection = nauseaAnswer.locator('.answer-section').filter({
    has: nauseaAnswer.getByText('Bạn cho mình biết thêm', { exact: true }),
  });
  const questionText = (await nauseaQuestionSection.innerText()).toLowerCase();
  if (!questionText.includes('nôn') || !questionText.includes('nước')) {
    throw new Error(`Nausea follow-up did not prioritize vomiting/hydration: ${questionText}`);
  }

  if (errors.length) throw new Error(errors.join('\n'));
  console.log('dialogue_policy_ui=PASS');
} finally {
  await browser.close();
}
