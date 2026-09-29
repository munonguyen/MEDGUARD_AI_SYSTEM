import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { selectPatientResponseSurface } from '../src/chat/responseAuthority.js';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const verifiedAnswer = {
  title: 'Deterministic title must stay hidden',
  summary: 'Deterministic summary must stay hidden',
  narrative: [
    { kind: 'paragraph', text: 'Writer verified narrative', emphasis: [] },
    { kind: 'paragraph', text: 'Bạn cho mình biết thêm: legacy hidden question', emphasis: [] },
  ],
};

const verified = selectPatientResponseSurface({
  answer: verifiedAnswer,
  verificationStatus: 'verified',
});
assert(verified.mode === 'canonical-narrative', 'verified response must select canonical narrative');
assert(verified.canonicalVerifiedResponse === true, 'verified narrative must be canonical');
assert(verified.narrativeBlocks.length === 1, 'legacy question narrative must be filtered');
assert(verified.narrativeBlocks[0].text === 'Writer verified narrative', 'wrong verified narrative selected');

for (const fallbackStatus of ['rejected', 'timed_out', 'unavailable', 'circuit_open', 'error', 'not_requested', 'shadow']) {
  const fallback = selectPatientResponseSurface({
    answer: verifiedAnswer,
    verificationStatus: fallbackStatus,
  });
  assert(
    fallback.mode === 'deterministic-fallback',
    `${fallbackStatus} must select deterministic fallback`,
  );
  assert(fallback.canonicalVerifiedResponse === false, `${fallbackStatus} cannot be canonical`);
}

const verifiedWithoutNarrative = selectPatientResponseSurface({
  answer: { title: 'Fallback', summary: 'Safe deterministic fallback', narrative: [] },
  verificationStatus: 'verified',
});
assert(
  verifiedWithoutNarrative.mode === 'deterministic-fallback',
  'verified metadata without narrative must fail safe to deterministic response',
);

const componentUrl = new URL('../src/chat/GroundedAnswer.jsx', import.meta.url);
const source = await readFile(fileURLToPath(componentUrl), 'utf8');
for (const fragment of [
  "selectPatientResponseSurface",
  'responseSurface.canonicalVerifiedResponse',
  'canonical-patient-response',
  'canonical-narrative',
  'deterministic-fallback-response',
]) {
  assert(source.includes(fragment), `GroundedAnswer integration missing: ${fragment}`);
}

console.log('V27 runtime patient-response authority contract: PASS');
