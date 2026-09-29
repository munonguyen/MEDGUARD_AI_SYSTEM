import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const componentUrl = new URL('../src/chat/GroundedAnswer.jsx', import.meta.url);
const source = await readFile(fileURLToPath(componentUrl), 'utf8');

const requiredFragments = [
  "responseMeta.verification_status === 'verified' && hasNarrative",
  'canonical-patient-response',
  'canonical-narrative',
  'deterministic-fallback-response',
];

for (const fragment of requiredFragments) {
  if (!source.includes(fragment)) {
    throw new Error(`V27 response authority contract missing: ${fragment}`);
  }
}

const canonicalBranch = source.indexOf('if (canonicalVerifiedResponse)');
const fallbackBranch = source.indexOf('// Deterministic / unavailable / rejected gateway fallback surface.');
if (canonicalBranch < 0 || fallbackBranch < 0 || canonicalBranch > fallbackBranch) {
  throw new Error('Verified canonical response must be selected before deterministic fallback rendering');
}

console.log('V27 canonical patient-response authority contract: PASS');
