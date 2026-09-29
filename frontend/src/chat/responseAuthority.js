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
