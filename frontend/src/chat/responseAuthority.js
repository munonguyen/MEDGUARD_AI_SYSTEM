const legacyQuestionPrefixes = [
  'Bạn cho mình biết thêm:',
  'Thông tin cần báo nhân viên y tế nếu có thể:',
];

export function isLegacyQuestionNarrative(block) {
  return legacyQuestionPrefixes.some((prefix) => block?.text?.startsWith(prefix));
}

export function selectPatientResponseSurface({ answer, verificationStatus }) {
  const rawNarrativeBlocks = Array.isArray(answer?.narrative) ? answer.narrative : [];
  const narrativeBlocks = rawNarrativeBlocks.filter((block) => !isLegacyQuestionNarrative(block));
  const canonicalVerifiedResponse = verificationStatus === 'verified' && narrativeBlocks.length > 0;

  return {
    mode: canonicalVerifiedResponse ? 'canonical-narrative' : 'deterministic-fallback',
    narrativeBlocks,
    canonicalVerifiedResponse,
  };
}

export function canonicalPatientResponseText({ answer, verificationStatus, fallbackText = '' }) {
  const surface = selectPatientResponseSurface({ answer, verificationStatus });
  if (surface.canonicalVerifiedResponse) {
    const text = surface.narrativeBlocks
      .map((block) => String(block?.text || '').trim())
      .filter(Boolean)
      .join('\n\n')
      .trim();
    if (text) return text;
  }
  return String(fallbackText || '').trim();
}
